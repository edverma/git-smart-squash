#!/usr/bin/env python3
"""
Test to reproduce the brace corruption issue reported in version 3.3.19.
This test creates a simple JavaScript file scenario and tracks where closing braces are lost.
"""

import tempfile
import os
import subprocess
import shutil
from git_smart_squash.diff_parser import parse_diff, create_hunk_patch, _create_absolutely_minimal_patch

def create_test_repo():
    """Create a test git repository with a JavaScript file."""
    temp_dir = tempfile.mkdtemp()
    os.chdir(temp_dir)
    
    # Initialize git repo
    subprocess.run(['git', 'init'], check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test'], check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@test.com'], check=True, capture_output=True)
    
    # Create initial JavaScript file
    js_content = """function example() {
    console.log("hello");
    return true;
}

export default example;
"""
    
    os.makedirs('src/lib', exist_ok=True)
    with open('src/lib/index.js', 'w') as f:
        f.write(js_content)
    
    subprocess.run(['git', 'add', '.'], check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], check=True, capture_output=True)
    
    # Modify the file to create changes
    modified_content = """function example() {
    console.log("hello");
    console.log("debug info");
    return true;
}

function newFunction() {
    console.log("new function");
    return false;
}

export default example;
"""
    
    with open('src/lib/index.js', 'w') as f:
        f.write(modified_content)
    
    return temp_dir

def test_brace_corruption():
    """Test for brace corruption in patch creation."""
    print("Creating test repository...")
    test_dir = create_test_repo()
    
    try:
        # Get the diff
        result = subprocess.run(['git', 'diff'], capture_output=True, text=True)
        base_diff = result.stdout
        
        print(f"Original diff has {base_diff.count('{')} open braces and {base_diff.count('}')} close braces")
        print("\nOriginal diff:")
        print("=" * 50)
        print(base_diff)
        print("=" * 50)
        
        # Parse hunks
        hunks = parse_diff(base_diff)
        print(f"\nParsed {len(hunks)} hunks:")
        for hunk in hunks:
            print(f"  Hunk {hunk.id}: lines {hunk.start_line}-{hunk.end_line}")
            print(f"    Content has {hunk.content.count('{')} open braces and {hunk.content.count('}')} close braces")
        
        # Create patch using current implementation
        print("\nTesting create_hunk_patch()...")
        patch = create_hunk_patch(hunks, base_diff)
        
        print(f"Generated patch has {patch.count('{')} open braces and {patch.count('}')} close braces")
        print("\nGenerated patch:")
        print("=" * 50)
        print(patch)
        print("=" * 50)
        
        # Test _create_absolutely_minimal_patch directly
        print("\nTesting _create_absolutely_minimal_patch() directly...")
        minimal_patch = _create_absolutely_minimal_patch(hunks, base_diff)
        
        print(f"Minimal patch has {minimal_patch.count('{')} open braces and {minimal_patch.count('}')} close braces")
        print("\nMinimal patch:")
        print("=" * 50)
        print(minimal_patch)
        print("=" * 50)
        
        # Verify brace preservation
        original_open = base_diff.count('{')
        original_close = base_diff.count('}')
        patch_open = patch.count('{')
        patch_close = patch.count('}')
        minimal_open = minimal_patch.count('{')
        minimal_close = minimal_patch.count('}')
        
        print(f"\nBrace count analysis:")
        print(f"Original:    {original_open} open, {original_close} close")
        print(f"Patch:       {patch_open} open, {patch_close} close")
        print(f"Minimal:     {minimal_open} open, {minimal_close} close")
        
        # Check for corruption
        if patch_open != patch_close:
            print("⚠️  CORRUPTION DETECTED: Unmatched braces in patch!")
            return False
        
        if patch_close < original_close:
            print("⚠️  CORRUPTION DETECTED: Missing closing braces in patch!")
            return False
            
        print("✅ No brace corruption detected")
        
        # Test if patch can be applied
        print("\nTesting patch application...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as pf:
            pf.write(patch)
            patch_file = pf.name
        
        try:
            result = subprocess.run(['git', 'apply', '--check', patch_file], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Patch can be applied successfully")
            else:
                print(f"❌ Patch application check failed: {result.stderr}")
                return False
        finally:
            os.unlink(patch_file)
        
        return True
        
    finally:
        os.chdir('/')
        shutil.rmtree(test_dir)

if __name__ == '__main__':
    print("Testing for brace corruption in git-smart-squash...")
    success = test_brace_corruption()
    if success:
        print("\n✅ Test passed - no corruption detected")
    else:
        print("\n❌ Test failed - corruption detected")