import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_pages  # noqa: E402


def make_checkout(root: Path, name: str, with_docs: bool = True) -> Path:
    checkout = root / name
    (checkout / "docs").mkdir(parents=True)
    if with_docs:
        (checkout / "zensical.toml").write_text("[project]\n", encoding="utf-8")
        (checkout / "docs" / "index.md").write_text("# Accueil\n", encoding="utf-8")
    return checkout


def fake_build(checkout: Path, uv: str = "uv") -> Path:
    site = checkout / "site"
    site.mkdir()
    (site / "index.html").write_text(f"{checkout.name}\n", encoding="utf-8")
    return site


class BuildPagesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.output = self.root / "_site"
        self.enterContext(mock.patch.object(build_pages, "build_docs", side_effect=fake_build))

    def test_publishes_main_at_root_and_develop_under_dev(self) -> None:
        prod, dev = make_checkout(self.root, "prod"), make_checkout(self.root, "dev")

        build_pages.build_pages(prod, dev, self.output)

        self.assertEqual((self.output / "index.html").read_text(encoding="utf-8"), "prod\n")
        self.assertEqual((self.output / "dev" / "index.html").read_text(encoding="utf-8"), "dev\n")

    def test_adds_banner_to_develop_only(self) -> None:
        prod, dev = make_checkout(self.root, "prod"), make_checkout(self.root, "dev")

        build_pages.build_pages(prod, dev, self.output)

        self.assertTrue((dev / "docs" / "index.md").read_text(encoding="utf-8").startswith(build_pages.DEV_BANNER))
        self.assertEqual((prod / "docs" / "index.md").read_text(encoding="utf-8"), "# Accueil\n")

    def test_redirects_to_dev_when_main_has_no_docs(self) -> None:
        prod, dev = make_checkout(self.root, "prod", with_docs=False), make_checkout(self.root, "dev")

        build_pages.build_pages(prod, dev, self.output)

        self.assertIn('url=dev/', (self.output / "index.html").read_text(encoding="utf-8"))
        self.assertTrue((self.output / "dev" / "index.html").is_file())

    def test_fails_when_no_branch_has_docs(self) -> None:
        prod = make_checkout(self.root, "prod", with_docs=False)
        dev = make_checkout(self.root, "dev", with_docs=False)

        with self.assertRaises(build_pages.PagesBuildError):
            build_pages.build_pages(prod, dev, self.output)

    def test_main_rejects_identical_checkouts(self) -> None:
        checkout = make_checkout(self.root, "same")

        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            build_pages.main(["--prod", str(checkout), "--dev", str(checkout)])


if __name__ == "__main__":
    unittest.main()
