class GitSmartSquash < Formula
  include Language::Python::Virtualenv

  desc "Automatically reorganize messy git commit histories into clean, semantic commits"
  homepage "https://github.com/edverma/git-smart-squash"
  url "https://github.com/edverma/git-smart-squash/archive/v2.3.0.tar.gz"
  sha256 "7f23364997473b7239ed46d6a46e1f3b28bc93d427fed1721195a85249275947"
  license "MIT"

  depends_on "python@3.12"

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/54/ed/79a089b6be93607fa5cdaedf301d7dfb23af5f25c398d5ead2525b063e17/pyyaml-6.0.2.tar.gz"
    sha256 "d584d9ec91ad65861cc08d42e834324ef890a082e591037abe114850ff7bbc3e"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/a1/53/830aa4c3066a8ab0ae9a9955976fb770fe9c6102117c8ec4ab3ea62d89e8/rich-14.0.0.tar.gz"
    sha256 "82f1bc23a6a21ebca4ae0c45af9bdbc492ed20231dcb63f297d6d1021a9d5725"
  end

  resource "openai" do
    url "https://files.pythonhosted.org/packages/ba/9b/946d67085cba123ab48198610d962d73d0c301b3771f21af7791eb07df93/openai-1.44.0.tar.gz"
    sha256 "acde74598976ec85bc477e9abb94eeb17f6efd998914d5685eeb46a69116894a"
  end

  resource "anthropic" do
    url "https://files.pythonhosted.org/packages/57/fd/8a9332f5baf352c272494a9d359863a53385a208954c1a7251a524071930/anthropic-0.52.0.tar.gz"
    sha256 "f06bc924d7eb85f8a43fe587b875ff58b410d60251b7dc5f1387b322a35bd67b"
  end

  resource "requests" do
    url "https://files.pythonhosted.org/packages/9d/be/10918a2eac4ae9f02f6cfe6414b7a155ccd8f7f9d4380d62fd5b955065c3/requests-2.31.0.tar.gz"
    sha256 "942c5a758f98d790eaed1a29cb6eefc7ffb0d1cf7af05c3d2791656dbd6ad1e1"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "usage: git-smart-squash", shell_output("#{bin}/git-smart-squash --help")
  end
end
