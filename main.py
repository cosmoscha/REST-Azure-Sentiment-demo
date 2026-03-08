from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests as req
import uvicorn
import logging
from opencensus.ext.azure.log_exporter import AzureLogHandler
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# --- Azure Key Vault Configuration ---
KEY_VAULT_URL = "https://rest-test-api-keys.vault.azure.net/"

try:
    credential = DefaultAzureCredential()
    secret_client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)

    AZURE_KEY = secret_client.get_secret("TextAnalyticsKey").value
    AZURE_ENDPOINT = secret_client.get_secret("TextAnalyticsEndpoint").value

    # NEW: Fetch your Application Insights connection string securely from the vault!
    APP_INSIGHTS_CONN_STR = secret_client.get_secret("AppInsightsConnString0").value

    print("Secrets successfully loaded from Azure Key Vault!")
except Exception as e:
    print(f"Failed to connect to Azure Key Vault: {e}")
    AZURE_KEY = None
    AZURE_ENDPOINT = None
    APP_INSIGHTS_CONN_STR = None

# --- Logger Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # 10 is DEBUG level

# If we successfully got the connection string from the vault, attach the Azure handler
if APP_INSIGHTS_CONN_STR:
    logger.addHandler(AzureLogHandler(connection_string=APP_INSIGHTS_CONN_STR))

app = FastAPI()


class Model(BaseModel):
    text_to_analyze: list[str]


@app.post("/analyze")
def analyze_text(data: Model):
    if not AZURE_KEY or not AZURE_ENDPOINT:
        raise HTTPException(status_code=500, detail="Server configuration error: Secrets not loaded.")

    base_url = AZURE_ENDPOINT.strip('/')
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # 1. Prepare documents for batched API request
    documents = [
        {"language": "en", "id": str(index + 1), "text": text}
        for index, text in enumerate(data.text_to_analyze)
    ]
    body = {"documents": documents}

    try:
        # 2. Make the API Calls
        kp_url = f"{base_url}/text/analytics/v3.0/keyPhrases"
        kp_response = req.post(kp_url, headers=headers, json=body)
        kp_response.raise_for_status()

        sentiment_url = f"{base_url}/text/analytics/v3.0/sentiment"
        sentiment_response = req.post(sentiment_url, headers=headers, json=body)
        sentiment_response.raise_for_status()

        # Extract the results lists
        keyphrases_results = kp_response.json().get("documents", [])
        sentiment_results = sentiment_response.json().get("documents", [])

        # 3. NEW: Log each processed text directly to Azure Application Insights
        # 3. NEW: Log each processed text directly to Azure Application Insights
        for i, text in enumerate(data.text_to_analyze):
            doc_id = str(i + 1)

            # Find the matching result for this specific document
            sent_doc = next((d for d in sentiment_results if d["id"] == doc_id), {})
            kp_doc = next((d for d in keyphrases_results if d["id"] == doc_id), {})

            # FIXED: We convert the keyPhrases list into a comma-separated string
            keyphrases_list = kp_doc.get("keyPhrases", [])
            keyphrases_string = ", ".join(keyphrases_list)

            log_data = {
                "custom_dimensions": {
                    "text": text,
                    "text_sentiment": sent_doc.get("sentiment", "unknown"),
                    "text_keyphrases": keyphrases_string  # Now passing a string!
                }
            }
            logger.info('Text Processed Successfully', extra=log_data)

        # 4. Return the combined response to the user
        return {
            "keyphrases": keyphrases_results,
            "sentiment": sentiment_results
        }

    except req.exceptions.RequestException as e:
        logger.error(f"Azure API request failed: {e}")
        return {"error": "Azure API request failed", "details": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)