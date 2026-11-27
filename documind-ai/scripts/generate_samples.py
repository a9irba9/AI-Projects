"""Generate synthetic business PDFs for demonstration and testing."""
from pathlib import Path
import fitz

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "storage" / "samples"


def create_pdf(filename: str, text: str) -> Path:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SAMPLES_DIR / filename
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 60), text, fontsize=11)
    doc.save(out_path)
    doc.close()
    return out_path


if __name__ == "__main__":
    p1 = create_pdf(
        "sample_invoice_1.pdf",
        "INVOICE\n"
        "Supplier: Nippon Precision Parts Co., Ltd.\n"
        "Contact: billing@nippon-precision.example\n"
        "Invoice Number: INV-001\n"
        "Document Date: 2026-11-01\n"
        "Due Date: 2026-12-01\n"
        "Customer: Tokyo Manufacturing KK\n"
        "Items:\n"
        "  1. Stainless Steel Sheets (Grade 304) x 50 @ $20.00 = $1,000.00\n"
        "Tax (10%): $100.00\n"
        "Total Amount: $1,100.00 USD\n"
        "Terms: Net 30 days via bank transfer.\n",
    )
    p2 = create_pdf(
        "sample_invoice_2.pdf",
        "INVOICE\n"
        "Supplier: Kanto Logistics Solutions\n"
        "Contact: accounts@kanto-logistics.example\n"
        "Invoice Number: INV-002\n"
        "Document Date: 2026-11-10\n"
        "Due Date: 2026-12-10\n"
        "Customer: Tokyo Manufacturing KK\n"
        "Items:\n"
        "  1. Express Freight & Customs Handling x 1 @ $450.00 = $450.00\n"
        "Tax (10%): $45.00\n"
        "Total Amount: $495.00 USD\n"
        "Terms: Net 30 days.\n",
    )
    print(f"Generated:\n  {p1}\n  {p2}")
