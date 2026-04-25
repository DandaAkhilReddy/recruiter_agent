param location string
param name string
param tags object
param logAnalyticsWorkspaceId string
param appInsightsConnectionString string
param acrLoginServer string
param acrName string
param keyVaultName string
param aoaiEndpoint string
param postgresHost string
param postgresUser string
param postgresDatabase string

@description('Container image (defaults to a placeholder; azd deploy overrides on each push).')
param containerImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: last(split(logAnalyticsWorkspaceId, '/'))
}

resource mi 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${name}-mi'
  location: location
  tags: tags
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: acrName
}

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var kvSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, mi.id, acrPullRoleId)
  scope: acr
  properties: {
    principalId: mi.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
  }
}

resource kvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, mi.id, kvSecretsUserRoleId)
  scope: kv
  properties: {
    principalId: mi.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRoleId)
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${name}-env'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: law.properties.customerId
        sharedKey: law.listKeys().primarySharedKey
      }
    }
  }
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: union(tags, { 'azd-service-name': 'backend' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${mi.id}': {} }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['*']
          allowedHeaders: ['*']
        }
      }
      registries: [{
        server: acrLoginServer
        identity: mi.id
      }]
      secrets: [
        {
          name: 'aoai-api-key'
          keyVaultUrl: '${kv.properties.vaultUri}secrets/aoai-api-key'
          identity: mi.id
        }
        {
          name: 'postgres-password'
          keyVaultUrl: '${kv.properties.vaultUri}secrets/postgres-password'
          identity: mi.id
        }
      ]
    }
    template: {
      containers: [{
        name: 'api'
        image: containerImage
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: [
          { name: 'ENV', value: 'prod' }
          { name: 'LOG_LEVEL', value: 'INFO' }
          { name: 'AOAI_ENDPOINT', value: aoaiEndpoint }
          { name: 'AOAI_API_KEY', secretRef: 'aoai-api-key' }
          { name: 'AOAI_GPT4O_DEPLOYMENT', value: 'gpt-4o' }
          { name: 'AOAI_GPT4O_MINI_DEPLOYMENT', value: 'gpt-4o-mini' }
          { name: 'AOAI_EMBEDDING_DEPLOYMENT', value: 'text-embedding-3-large' }
          { name: 'AOAI_EMBEDDING_DIMENSIONS', value: '1536' }
          // App composes DATABASE_URL at startup from these four pieces:
          { name: 'POSTGRES_HOST', value: postgresHost }
          { name: 'POSTGRES_USER', value: postgresUser }
          { name: 'POSTGRES_DATABASE', value: postgresDatabase }
          { name: 'POSTGRES_PASSWORD', secretRef: 'postgres-password' }
          { name: 'POSTGRES_SSL', value: 'require' }
          { name: 'CORS_ALLOW_ORIGINS', value: '*' }
          { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
        ]
      }]
      scale: {
        minReplicas: 0
        maxReplicas: 3
        rules: [{
          name: 'http-rule'
          http: { metadata: { concurrentRequests: '50' } }
        }]
      }
    }
  }
  dependsOn: [acrPull, kvSecretsUser]
}

output fqdn string = 'https://${app.properties.configuration.ingress.fqdn}'
output managedIdentityId string = mi.id
