from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests as req
import uvicorn
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


KEY_VAULT_URL = "https://rest-test-api-keys.vault.azure.net/"


try:
    credential = DefaultAzureCredential()
    secret_client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)

    AZURE_KEY = secret_client.get_secret("TextAnalyticsKey").value
    AZURE_ENDPOINT = secret_client.get_secret("TextAnalyticsEndpoint").value
    print("Secrets successfully loaded from Azure Key Vault!")
except Exception as e:
    print(f"Failed to connect to Azure Key Vault: {e}")
    AZURE_KEY = None
    AZURE_ENDPOINT = None

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

    documents = [
        {"language": "en", "id": str(index + 1), "text": text}
        for index, text in enumerate(data.text_to_analyze)
    ]
    body = {"documents": documents}

    try:
        kp_url = f"{base_url}/text/analytics/v3.0/keyPhrases"
        kp_response = req.post(kp_url, headers=headers, json=body)
        kp_response.raise_for_status()

        sentiment_url = f"{base_url}/text/analytics/v3.0/sentiment"
        sentiment_response = req.post(sentiment_url, headers=headers, json=body)
        sentiment_response.raise_for_status()

        return {
            "keyphrases": kp_response.json().get("documents", []),
            "sentiment": sentiment_response.json().get("documents", [])
        }

    except req.exceptions.RequestException as e:
        return {"error": "Azure API request failed", "details": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)