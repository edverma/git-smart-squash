class GitSmartSquash < Formula
  include Language::Python::Virtualenv

  desc "Automatically reorganize messy git commit histories into clean, semantic commits"
  homepage "https://github.com/edverma/git-smart-squash"
  url "https://files.pythonhosted.org/packages/source/g/git-smart-squash/git_smart_squash-1.3.4.tar.gz"
  sha256 "a1d65d94f4a3a45a80e65b3242f13a0bc889d67e1fc235c0ffec3dad2b34c9aa"
  license "MIT"

  depends_on "python@3.12"

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/cd/e5/af35f7ea75cf72f2cd079c95ee16797de7cd71f29ea7c68ae5ce7be1eda2b/PyYAML-6.0.2.tar.gz"
    sha256 "d584d9ec91ad65861cc08d42e834324ef890a082e591037abe114850ff7bbc3e"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/87/67/a37f6214d0e9fe57f6a3427b2d0b2b6e8d8f87a0b8a62b8a77ad8f6c5ee2/rich-14.0.0.tar.gz"
    sha256 "8260cda28e3db6bf04d2d1ef4dbc03ba80a824c88b0e7668a0f23126a424844a"
  end

  resource "openai" do
    url "https://files.pythonhosted.org/packages/source/o/openai/openai-1.44.0.tar.gz"
    sha256 "68a5fbc86e5c2eed8b93de9e4b9d574a0b4c9b4ae9b21b2d394e9d8e7ebcdf17"
  end

  resource "anthropic" do
    url "https://files.pythonhosted.org/packages/source/a/anthropic/anthropic-0.52.0.tar.gz"
    sha256 "52d60cdbf8964daf2e8a5a4f2b8e7ac5e4da4915a67e1bd1987fa5e6f5e4a87a"
  end

  resource "requests" do
    url "https://files.pythonhosted.org/packages/source/r/requests/requests-2.31.0.tar.gz"
    sha256 "942c5a758f98d790eaed1a29cb6eefc7ffb0d1cf7af05c3d2791656dbd6ad1e1"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "usage: git-smart-squash", shell_output("#{bin}/git-smart-squash --help")
    assert_match "Zero-friction git commit squashing", shell_output("#{bin}/gss --help")
  end
end