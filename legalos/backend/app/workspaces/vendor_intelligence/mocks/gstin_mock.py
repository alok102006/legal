import random
from typing import Dict, Any

# Hardcoded demo GSTIN triggers for fraud flags
FRAUD_GSTINS = {
    "27AAAAA1111A1Z1": {
        "company_name": "Apex Shell Logistics Pvt Ltd",
        "is_valid": False,
        "registration_date": "2023-01-15",
        "trust_score": 8,
        "fraud_flagged": True,
        "reason": "Entity flagged by GST Network (GSTN) as a high-risk dummy firm used for circular trading and ITC tax credit evasion.",
        "lgnm": "Apex Shell Logistics Pvt Ltd",
        "tradeNam": "Apex Shell Logistics",
        "sts": "Cancelled",
        "dty": "Regular",
        "ctb": "Private Limited Company",
        "rgdt": "15/01/2023",
        "stj": "Ward 42",
        "ctj": "Range III",
        "nba": ["Transport Services", "Logistics", "Warehousing"],
        "pradr": {
            "addr": {
                "bno": "Building No 45B",
                "bnm": "Shivaji Udyog Nagar",
                "flno": "Ground Floor",
                "st": "LBS Marg",
                "loc": "Kurla West, Mumbai",
                "dst": "Mumbai",
                "stcd": "Maharashtra",
                "pncd": "400070"
            },
            "ntr": "Service Provider"
        }
    },
    "27BBBBB2222B2Z2": {
        "company_name": "Karnavati Steel Trading",
        "is_valid": True,
        "registration_date": "2020-06-18",
        "trust_score": 29,
        "fraud_flagged": True,
        "reason": "Multiple compliance delay notices served. Substituted active PAN holder with blacklisted directors.",
        "lgnm": "Karnavati Steel Trading Private Limited",
        "tradeNam": "Karnavati Steel",
        "sts": "Active",
        "dty": "Regular",
        "ctb": "Private Limited Company",
        "rgdt": "18/06/2020",
        "stj": "Ward 12",
        "ctj": "Range I",
        "nba": ["Wholesale Trade", "Iron & Steel Manufacturing"],
        "pradr": {
            "addr": {
                "bno": "Shop No 12",
                "bnm": "Steel Market Complex",
                "flno": "First Floor",
                "st": "Kalupur Road",
                "loc": "Ahmedabad",
                "dst": "Ahmedabad",
                "stcd": "Gujarat",
                "pncd": "380001"
            },
            "ntr": "Wholesale Business"
        }
    }
}

class VendorVerificationProvider:
    """Mock verification client for Indian GSTIN compliance audit."""

    @staticmethod
    def verify_gstin(gstin: str) -> Dict[str, Any]:
        """
        # MOCKED — replace with real GSTIN verification API integration
        Simulates call to a government GSTIN registry.
        """
        # Cleanup input
        clean_gstin = gstin.upper().strip()

        # 1. Check if it's one of the deterministic fraud triggers
        if clean_gstin in FRAUD_GSTINS:
            payload = FRAUD_GSTINS[clean_gstin]
            return {
                "gstin": clean_gstin,
                **payload
            }

        # 2. Validate format (India GSTIN is exactly 15 characters long)
        if len(clean_gstin) != 15:
            return {
                "gstin": clean_gstin,
                "company_name": "Unknown Entity",
                "is_valid": False,
                "registration_date": None,
                "trust_score": 0,
                "fraud_flagged": False,
                "reason": "Invalid GSTIN format. Must be exactly 15 characters."
            }

        # 3. Standard successful lookup mock generator
        # Trust score for unrecognized (but format-valid) GSTINs: random.randint(40, 95)
        trust_score = random.randint(40, 95)
        
        # Determine company name based on a portion of the GSTIN (PAN part) for demo consistency
        pan_slug = clean_gstin[2:7]
        company_name = f"Vardhaman Ind-Commercial {pan_slug} Corp"
        
        return {
            "gstin": clean_gstin,
            "company_name": company_name,
            "is_valid": True,
            "registration_date": "2019-11-20",
            "trust_score": trust_score,
            "fraud_flagged": False,
            "reason": "Entity verified successfully with active status.",
            "lgnm": company_name,
            "tradeNam": f"Vardhaman {pan_slug}",
            "sts": "Active",
            "dty": "Regular",
            "ctb": "Partnership Firm",
            "rgdt": "20/11/2019",
            "stj": "Ward 8",
            "ctj": "Range V",
            "nba": ["Trading", "Retail Sales"],
            "pradr": {
                "addr": {
                    "bno": "Plot 104",
                    "bnm": "Vardhaman Heights",
                    "flno": "Suite 401",
                    "st": "M.G. Road",
                    "loc": "Pune",
                    "dst": "Pune",
                    "stcd": "Maharashtra",
                    "pncd": "411001"
                },
                "ntr": "Retailer"
            }
        }
