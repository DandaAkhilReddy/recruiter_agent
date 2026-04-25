param location string
param name string
param tags object

resource swa 'Microsoft.Web/staticSites@2023-12-01' = {
  name: name
  location: location
  tags: union(tags, { 'azd-service-name': 'frontend' })
  sku: { name: 'Free', tier: 'Free' }
  properties: {
    buildProperties: {
      appLocation: '/'
      outputLocation: 'out'
      apiLocation: ''
    }
  }
}

output defaultHostname string = 'https://${swa.properties.defaultHostname}'
output name string = swa.name
