from pathlib import Path
import requests

PAPERS = {
    "attention_v7.pdf": "https://arxiv.org/pdf/1706.03762v7",
    "moshi_v1.pdf": "https://arxiv.org/pdf/2410.00037v1",
    "dynamic_chunking_v2.pdf": "https://arxiv.org/pdf/2507.07955v2",
}

def main():
    folder = Path("papers")
    folder.mkdir(exist_ok=True)
    for name, url in PAPERS.items():
        path = folder / name
        response = requests.get(url, timeout=90)
        response.raise_for_status()
        if not response.content.startswith(b"%PDF"):
            raise RuntimeError(f"{url} did not return a PDF")
        path.write_bytes(response.content)
        print(f"Downloaded {name}: {len(response.content):,} bytes")

if __name__ == "__main__":
    main()
