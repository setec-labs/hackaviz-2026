"""Assemble the GitHub Pages site from two checkouts of the repository.

The documentation of `main` (prod) is published at the root of the site and the documentation of
`develop` under `/dev/`. GitHub Pages hosts a single site, so both versions are rebuilt together on
every deployment.

    python scripts/build_pages.py --prod <main checkout> --dev <develop checkout> --output _site
"""

import argparse
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

DEV_PREFIX = "dev"
DEV_BANNER = (
    '!!! warning "Documentation de développement"\n'
    "    Version de la branche `develop`, susceptible de changer. "
    "La version stable est [ici](../).\n\n"
)
NO_PROD_PAGE = """<!doctype html>
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=dev/">
<title>Hackaviz Mobilités 2026</title>
<p>Pas encore de version stable : <a href="dev/">documentation de développement</a>.</p>
"""


class PagesBuildError(RuntimeError):
    pass


def has_docs(checkout: Path) -> bool:
    return (checkout / "zensical.toml").is_file()


def add_dev_banner(checkout: Path) -> None:
    index = checkout / "docs" / "index.md"
    index.write_text(DEV_BANNER + index.read_text(encoding="utf-8"), encoding="utf-8")


def build_docs(checkout: Path, uv: str = "uv") -> Path:
    # Isolated environment with the dev group only: never touches the checkout's own .venv.
    subprocess.run(
        [uv, "run", "--only-group", "dev", "--locked", "--isolated", "zensical", "build", "--clean", "--strict"],
        cwd=checkout,
        check=True,
    )
    return checkout / "site"


def assemble(prod_site: Path | None, dev_site: Path | None, output: Path) -> None:
    if prod_site is None and dev_site is None:
        raise PagesBuildError("Neither main nor develop contains the documentation")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    if prod_site is not None:
        shutil.copytree(prod_site, output, dirs_exist_ok=True)
    else:
        (output / "index.html").write_text(NO_PROD_PAGE, encoding="utf-8")
    if dev_site is not None:
        shutil.copytree(dev_site, output / DEV_PREFIX)


def build_pages(prod: Path, dev: Path, output: Path, uv: str = "uv") -> None:
    prod_site = build_docs(prod, uv) if has_docs(prod) else None
    dev_site = None
    if has_docs(dev):
        add_dev_banner(dev)
        dev_site = build_docs(dev, uv)
    for name, site in (("main", prod_site), ("develop", dev_site)):
        if site is None:
            print(f"::warning::No documentation on the {name} branch yet")
    assemble(prod_site, dev_site, output)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the GitHub Pages site (main at /, develop at /dev/).")
    parser.add_argument("--prod", type=Path, required=True, help="checkout of the main branch")
    parser.add_argument("--dev", type=Path, required=True, help="checkout of the develop branch")
    parser.add_argument("--output", type=Path, default=Path("_site"))
    parser.add_argument("--uv", default="uv")
    args = parser.parse_args(argv)
    if args.prod.resolve() == args.dev.resolve():
        parser.error("--prod and --dev must be distinct checkouts (the dev banner edits docs/index.md)")
    try:
        build_pages(args.prod, args.dev, args.output, args.uv)
    except PagesBuildError as exc:
        print(f"::error::{exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
