import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.config import settings
from app.workspaces.vendor_intelligence.mocks.gstin_mock import VendorVerificationProvider
from app.workspaces.vendor_intelligence import service, repository


def test_gstin_mock_provider_fraud_detection():
    """Verify that gstin_mock identifies fraud-flagged GSTINs correctly."""
    # Apex Shell Logistics check
    res_fraud_1 = VendorVerificationProvider.verify_gstin("27AAAAA1111A1Z1")
    assert res_fraud_1["fraud_flagged"] is True
    assert res_fraud_1["is_valid"] is False
    assert "circular trading" in res_fraud_1["reason"]

    # Karnavati Steel check
    res_fraud_2 = VendorVerificationProvider.verify_gstin("27BBBBB2222B2Z2")
    assert res_fraud_2["fraud_flagged"] is True
    assert res_fraud_2["is_valid"] is True
    assert res_fraud_2["trust_score"] < 30


def test_gstin_mock_provider_standard_validation():
    """Verify standard GSTIN mock generation rules."""
    # Invalid length GSTIN
    res_invalid = VendorVerificationProvider.verify_gstin("12345")
    assert res_invalid["is_valid"] is False
    assert res_invalid["trust_score"] == 0

    # Normal valid lookup
    res_valid = VendorVerificationProvider.verify_gstin("27ABCDE1234F1Z5")
    assert res_valid["is_valid"] is True
    assert res_valid["fraud_flagged"] is False
    assert 40 <= res_valid["trust_score"] <= 95
    assert "Vardhaman Ind-Commercial" in res_valid["company_name"]


@pytest.mark.asyncio
async def test_vendor_service_logging():
    """Verify that service correctly routes verify requests and invokes db repository logs."""
    original_mode = settings.sandbox_co_mode
    settings.sandbox_co_mode = "mock"
    try:
        # Mock database session
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        
        # Real user UUID
        user_id = uuid.uuid4()
        gstin = "27AAAAA1111A1Z1"

        # Call service
        result = await service.verify_and_log_vendor(
            session=mock_session,
            gstin=gstin,
            user_id=user_id
        )

        # Verify that add was called in session
        assert mock_session.add.call_count == 1
        assert result.gstin == gstin
        assert result.fraud_flagged is True
        assert result.company_name == "Apex Shell Logistics Pvt Ltd"
    finally:
        settings.sandbox_co_mode = original_mode


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_sandbox_authentication(mock_post):
    """Verify that get_sandbox_token authenticates successfully and caches the token."""
    from app.workspaces.vendor_intelligence import sandbox_client
    
    # 1. Reset client globals
    sandbox_client._token_cache = None
    sandbox_client._token_expiry = 0.0
    
    # Configure key settings for test context
    settings.sandbox_co_api_key = "test_key"
    settings.sandbox_co_api_secret = "test_secret"
    
    # 2. Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "code": 200,
        "data": {
            "access_token": "mocked_jwt_token_123"
        }
    }
    mock_post.return_value = mock_response

    # 3. Call token retrieval
    token1 = await sandbox_client.get_sandbox_token()
    assert token1 == "mocked_jwt_token_123"
    assert mock_post.call_count == 1
    
    # 4. Check cache hit (mock_post should not be called again)
    token2 = await sandbox_client.get_sandbox_token()
    assert token2 == "mocked_jwt_token_123"
    assert mock_post.call_count == 1


@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_sandbox_search_gstin_live(mock_post):
    """Verify that search_gstin_live queries public registry and returns taxpayer details."""
    from app.workspaces.vendor_intelligence import sandbox_client
    
    sandbox_client._token_cache = "cached_token"
    sandbox_client._token_expiry = 9999999999.0
    settings.sandbox_co_api_key = "test_key"
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "code": 200,
        "data": {
            "data": {
                "gstin": "24ABKCS2033B1ZV",
                "legalName": "Sandbox Tech Pvt Ltd",
                "status": "Active",
                "regStartDate": "06/02/2023"
            }
        }
    }
    mock_post.return_value = mock_response

    data = await sandbox_client.search_gstin_live("24ABKCS2033B1ZV")
    assert data["legalName"] == "Sandbox Tech Pvt Ltd"
    assert data["status"] == "Active"
    assert mock_post.call_count == 1


@pytest.mark.asyncio
@patch("app.workspaces.vendor_intelligence.sandbox_client.search_gstin_live")
async def test_sandbox_live_routing(mock_search):
    """Verify that service routes requests to live client when mode is set to live."""
    # Configure mode to live
    original_mode = settings.sandbox_co_mode
    settings.sandbox_co_mode = "live"
    
    try:
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        user_id = MagicMock()
        
        # Configure search return value
        mock_search.return_value = {
            "gstin": "24ABKCS2033B1ZV",
            "legalName": "Sandbox Tech Pvt Ltd",
            "status": "Active",
            "regStartDate": "06/02/2023"
        }
        
        result = await service.verify_and_log_vendor(
            session=mock_session,
            gstin="24ABKCS2033B1ZV",
            user_id=user_id
        )
        
        assert result.company_name == "Sandbox Tech Pvt Ltd"
        assert result.is_valid is True
        assert result.trust_score == 70
        assert result.fraud_flagged is False
        # Verify regStartDate was formatted parsed to YYYY-MM-DD
        assert str(result.registration_date) == "2023-02-06"
        assert mock_search.call_count == 1
    finally:
        # Restore original configuration
        settings.sandbox_co_mode = original_mode

