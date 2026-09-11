# Azure Container Deployment Guide: Policy Detective Backend

Deploying the **Policy Detective Backend** with Docker on **Microsoft Azure** resolves the 50-second cold starts and resource throttling of Render's free tier.

---

## Recommended Target: Azure Container Apps (ACA)

| Feature | Render Free Tier | Azure Container Apps |
|---|---|---|
| **Cold Starts** | 50–90 seconds sleep | Instant (with `min-replicas=1`) or ~2-3s |
| **Cost** | Free (slow & sleeps) | **Free Monthly Grant** (180,000 vCPU-sec, 360,000 GiB-sec, 2M requests/mo) |
| **HTTPS/TLS** | Auto | Auto (`*.azurecontainerapps.io`) |
| **Compute Scaling** | Fixed 512 MB | 0.5 – 4.0 vCPU, 1.0 – 8.0 GB RAM |
| **Docker Support** | Limited / Buildpack | Full Native Dockerfile (Python + Node.js + WebCMD) |

---

## Path 1: Instant Deployment via Azure Cloud Shell (Zero Local Installs)

If you do not have Docker Desktop or Azure CLI installed on your local Windows PC, you can deploy in 5 minutes using the **Azure Cloud Shell** directly in your browser:

1. Log into [portal.azure.com](https://portal.azure.com).
2. Click the **Cloud Shell** icon (`>_`) in the top navigation bar (or visit [shell.azure.com](https://shell.azure.com)). Select **Bash**.
3. In Cloud Shell, clone your repository and navigate into it:
   ```bash
   git clone https://github.com/jonvikboi/policy-detective.git
   cd policy-detective
   ```
4. Run the single-command deployment:
   ```bash
   az containerapp up \
     --name policy-detective-api \
     --resource-group rg-policydetective \
     --location eastus \
     --environment env-policydetective \
     --ingress external \
     --target-port 8000 \
     --source .
   ```
   > `az containerapp up` automatically creates an Azure Container Registry (ACR), builds the Dockerfile in the cloud, provisions the Container App environment, and exposes your backend with a public HTTPS URL.

5. Set your environment variables and secrets:
   ```bash
   az containerapp update \
     --name policy-detective-api \
     --resource-group rg-policydetective \
     --set-env-vars \
       GROQ_API_KEY="your_groq_api_key" \
       MONGODB_URI="your_mongodb_connection_string" \
       DATABASE_TYPE="mongodb" \
       LLM_MODEL="qwen/qwen3.6-27b" \
       LLM_PROVIDER="groq" \
       WEBCMD_BINARY="webcmd"
   ```

6. To keep the backend warm and eliminate cold starts completely:
   ```bash
   az containerapp update \
     --name policy-detective-api \
     --resource-group rg-policydetective \
     --min-replicas 1 \
     --max-replicas 3
   ```

---

## Path 2: Azure CLI from Your Local Terminal

If you install the [Azure CLI](https://aka.ms/installazurecliwindows) (`winget install Microsoft.AzureCLI` or MSI installer):

### 1. Login to Azure
```powershell
az login
```

### 2. Create Resource Group & Container Registry (ACR)
```powershell
az group create --name rg-policydetective --location eastus
az acr create --resource-group rg-policydetective --name acrpolicydetective$((Get-Random -Minimum 1000 -Maximum 9999)) --sku Basic --admin-enabled true
```
*(Store the registry name, e.g. `acrpolicydetective1234`)*

### 3. Build the Image in the Cloud (No Local Docker Required!)
Azure Container Registry can build the Dockerfile for you remotely:
```powershell
az acr build --registry <ACR_NAME> --image policy-detective-backend:latest .
```

### 4. Create Azure Container Apps Environment & Deploy
```powershell
# Create Container Apps managed environment
az containerapp env create `
  --name env-policydetective `
  --resource-group rg-policydetective `
  --location eastus

# Deploy the container app
az containerapp create `
  --name policy-detective-api `
  --resource-group rg-policydetective `
  --environment env-policydetective `
  --image <ACR_NAME>.azurecr.io/policy-detective-backend:latest `
  --target-port 8000 `
  --ingress external `
  --min-replicas 1 `
  --max-replicas 3 `
  --cpu 0.5 `
  --memory 1.0Gi `
  --registry-server <ACR_NAME>.azurecr.io `
  --env-vars `
    GROQ_API_KEY="<YOUR_GROQ_API_KEY>" `
    MONGODB_URI="<YOUR_MONGODB_URI>" `
    DATABASE_TYPE="mongodb" `
    LLM_MODEL="qwen/qwen3.6-27b" `
    LLM_PROVIDER="groq" `
    WEBCMD_BINARY="webcmd"
```

### 5. Get Your API URL
```powershell
az containerapp show `
  --name policy-detective-api `
  --resource-group rg-policydetective `
  --query properties.configuration.ingress.fqdn `
  --output tsv
```
This will print your public HTTPS endpoint:
`https://policy-detective-api.<generated-region-id>.eastus.azurecontainerapps.io`

---

## Path 3: Continuous Deployment via GitHub Actions

To automatically redeploy to Azure whenever you push code to `main`:

1. In GitHub, go to **Settings > Secrets and variables > Actions**.
2. Add the following repository secrets:
   - `AZURE_CREDENTIALS` (Service principal JSON from `az ad sp create-for-rbac`)
   - `REGISTRY_LOGIN_SERVER` (`<acr_name>.azurecr.io`)
   - `REGISTRY_USERNAME` (ACR username)
   - `REGISTRY_PASSWORD` (ACR password)
   - `GROQ_API_KEY`
   - `MONGODB_URI`
3. Push to `main`, and GitHub Actions will build and deploy automatically.

---

## Connecting the Frontend

Once the Azure backend is deployed:

1. Update your Vercel (or Render frontend) environment variable:
   - Key: `VITE_API_BASE_URL`
   - Value: `https://policy-detective-api.<your-hash>.eastus.azurecontainerapps.io`
2. Trigger a frontend redeploy on Vercel.
3. Verify by visiting `https://your-frontend-domain/health` or running a test scan.
