"""Small realistic contract fixtures with *known* planted issues (used by engine tests)."""

SUPPLY_AGREEMENT = """SUPPLY AGREEMENT

This Supply Agreement is made on 1st April 2026 between Kumar Auto Components Private Limited, having its registered office at Pune, Maharashtra ("Buyer") and Shree Steel Traders, having its office at Mumbai ("Supplier").

1. SCOPE OF SUPPLY
The Supplier shall supply mild steel sheets as per the Purchase Orders issued by the Buyer from time to time.

2. PRICE AND PAYMENT
2.1 Prices are as set out in Schedule A. The Supplier may revise the prices at any time by giving 7 days' written notice to the Buyer.
2.2 The Buyer shall pay each invoice within 60 days of receipt of the invoice.
2.3 Delayed payment shall carry interest at 24% per annum.

3. DELIVERY
The Supplier shall deliver the goods within 30 days of each Purchase Order. Time is not of the essence.

4. TERM AND TERMINATION
4.1 This Agreement shall be valid for 3 years and shall automatically renew for successive periods of 3 years unless either party gives 90 days' notice before expiry.
4.2 The Supplier may terminate this Agreement at any time on 15 days' notice. The Buyer may not terminate this Agreement before the expiry of the term.

5. LIABILITY AND INDEMNITY
The Buyer shall indemnify the Supplier against all losses, claims and expenses of whatever nature arising out of this Agreement, without limit.

6. GOVERNING LAW
This Agreement shall be governed by the laws of Singapore and the courts of Singapore shall have exclusive jurisdiction.

7. MISCELLANEOUS
This Agreement constitutes the entire agreement between the parties. Any amendment must be in writing and signed by both parties.

IN WITNESS WHEREOF the parties have executed this Agreement on the date first written above.
"""

# Same agreement, but fair: should not trigger most rules.
BALANCED_AGREEMENT = """SERVICE AGREEMENT

This Service Agreement is made on 1st May 2026 between Kumar Auto Components Private Limited ("Client") and Bright Consulting LLP ("Consultant").

1. SERVICES
The Consultant shall provide the services described in Schedule A.

2. FEES AND PAYMENT
The Client shall pay each undisputed invoice within 30 days of receipt. Late payments carry simple interest at 12% per annum.

3. TERM AND TERMINATION
This Agreement runs for 12 months. Either party may terminate for convenience on 30 days' written notice.

4. LIABILITY
Each party's total liability under this Agreement is limited to the fees paid in the preceding 12 months, except for fraud and wilful misconduct.

5. GOVERNING LAW AND DISPUTES
This Agreement is governed by the laws of India. Disputes shall be referred to arbitration by a sole arbitrator mutually appointed by the parties, seated at Pune.

6. STAMP DUTY
This Agreement is executed on stamp paper of the appropriate value as required under the Maharashtra Stamp Act.
"""
