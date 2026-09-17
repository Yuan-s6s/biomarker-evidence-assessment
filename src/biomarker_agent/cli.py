from __future__ import annotations

import argparse
from pathlib import Path

from biomarker_agent.pipeline import load_request, run_validation
from biomarker_agent.reporting import write_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local biomarker validation")
    parser.add_argument("request", type=Path)
    parser.add_argument("--out", type=Path, default=Path("reports/latest"))
    args = parser.parse_args()
    result = run_validation(load_request(args.request))
    json_path, markdown_path, html_path = write_outputs(result, args.out)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    print(f"Wrote {html_path}")


if __name__ == "__main__":
    main()
