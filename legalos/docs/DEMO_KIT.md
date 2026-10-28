# Demo kit (28 Oct 2026)

Folder `docs/demo_kit/` holds the three papers Ramesh Kulkarni would actually have on his desk. The demo company is
wiped clean except for these three, already analysed, plus the compliance calendar. Login
`ramesh@kulkarnitextiles.in` / `Kulkarni@2026`.

| File | Use in | What it shows |
|---|---|---|
| 01_Yarn_Supply_Agreement_Patel_Yarn_Traders.pdf | Contracts | 13 findings: unlimited indemnity, supplier can change prices at will, one-sided termination, Rs 2 lakh shortfall penalty, 24% interest |
| 02_Legal_Notice_Mehta_Associates.pdf | Notices | Cheque bounce, Rs 2,40,000, 15 days, reply by 12 Nov, section 138 NI Act |
| 03_Employee_Handbook_Kulkarni_Textiles.pdf | Documents | Ask: notice period for managers (60 days), paid leave (24 days), working week (48 hours) |
| GSTIN 27AAACT2727Q1ZW (type it) | Vendors | Live registry: Tata Motors, Active |

Rebuild the PDFs: `python scripts/make_demo_kit.py`. Reload everything: wipe via the UI or `scripts/reset_data.py`, then upload the three files.
The storyline and the exact clicks are in `docs/DEMO_PITCH.md`.
