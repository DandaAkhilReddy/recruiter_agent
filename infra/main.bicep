// Recruiter Agent — Azure infra (azd-compatible).
// Deploys: Log Analytics + App Insights, ACR, Key Vault, Postgres Flex (pgvector),
// Container Apps Environment + Container App (backend), Static Web App (frontend).
//
// AOAI deployments are intentionally created manually in the portal to avoid
// quota dance during `azd up`. Endpoint + key are passed in as params.

targetScope = 'resourceGroup'

@description('Environment name (e.g., demo, dev, prod). Used in resource naming.')
param environmentName string = 'demo'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Tag to apply to every resource for azd identification.')
param azdEnvName string = environmentName

@description('Postgres admin login.')
param postgresAdminUser string = 'pgadmin'

@secure()
@description('Postgres admin password (stored in Key Vault).')
param postgresAdminPassword string

@description('Azure OpenAI endpoint URL.')
param aoaiEndpoint string

@secure()
@description('Azure OpenAI API key.')
param aoaiApiKey string

var resourceToken = uniqueString(subscription().id, resourceGroup().id, environmentName)
var prefix = 'recruit-${environmentName}'
var tags = {
  'azd-env-name': azdEnvName
  app: 'recruiter-agent'
  env: environmentName
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    name: '${prefix}-mon'
    tags: tags
  }
}

module acr 'modules/acr.bicep' = {
  name: 'acr'
  params: {
    location: location
    name: replace('${prefix}acr${resourceToken}', '-', '')
    tags: tags
  }
}

module kv 'modules/keyvault.bicep' = {
  name: 'kv'
  params: {
    location: location
    name: 'kv-${resourceToken}'
    tags: tags
    aoaiApiKey: aoaiApiKey
    postgresPassword: postgresAdminPassword
  }
}

module pg 'modules/postgres.bicep' = {
  name: 'pg'
  params: {
    location: location
    name: '${prefix}-pg-${resourceToken}'
    tags: tags
    adminUser: postgresAdminUser
    adminPassword: postgresAdminPassword
    databaseName: 'recruiter'
  }
}

module aca 'modules/containerapp.bicep' = {
  name: 'aca'
  params: {
    location: location
    name: '${prefix}-api'
    tags: tags
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    acrLoginServer: acr.outputs.loginServer
    acrName: acr.outputs.name
    keyVaultName: kv.outputs.name
    aoaiEndpoint: aoaiEndpoint
    postgresHost: pg.outputs.fqdn
    postgresUser: postgresAdminUser
    postgresDatabase: 'recruiter'
  }
}

module swa 'modules/staticwebapp.bicep' = {
  name: 'swa'
  params: {
    location: 'eastus2'
    name: '${prefix}-web'
    tags: tags
  }
}

output BACKEND_URL string = aca.outputs.fqdn
output FRONTEND_URL string = swa.outputs.defaultHostname
output ACR_LOGIN_SERVER string = acr.outputs.loginServer
output KEY_VAULT_NAME string = kv.outputs.name
output POSTGRES_FQDN string = pg.outputs.fqdn
