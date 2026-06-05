"""GraphQL query strings for Team 12 CriticalAsset hydration."""

TOKEN_MUTATION = """
mutation ApplicationToken($input: ApplicationClientCredentialsInput!) {
  applicationClientCredentialsToken(input: $input) {
    accessToken
    refreshToken
    tokenType
    expiresIn
    scope
  }
}
"""

REFRESH_MUTATION = """
mutation RefreshApplicationToken($refreshToken: String!) {
  applicationRefreshToken(refreshToken: $refreshToken) {
    accessToken
    refreshToken
    tokenType
    expiresIn
    scope
  }
}
"""

WORK_ORDERS = """
query FetchWorkOrders($limit: Int!, $offset: Int) {
  workOrders(limit: $limit, offset: $offset) {
    totalCount
    nodes {
      id
      title
      description
      severity
      executionPriority
      startDate
      endDate
      locationId
      locationAddress
      workOrderType
      workOrderServiceCategory
      workOrderStageId
      workOrderStage { id name }
      asset { id name status serialNumber }
      location { id locationName address }
      assignees { id name email }
      createdAt
      updatedAt
    }
  }
}
"""

ASSETS = """
query ListAssets($limit: Int!, $offset: Int) {
  assets(limit: $limit, offset: $offset) {
    total
    assets {
      id
      name
      status
      serialNumber
      installationDate
      locations { id locationName address }
    }
  }
}
"""

LOCATIONS = """
query FetchLocations {
  locations {
    id
    locationName
    address
    parentId
    locationType { id name }
  }
}
"""

LOCATIONS_TREE = """
query FetchLocationsTree {
  locationsTree {
    id
    locationName
    address
    children { id locationName address }
  }
}
"""

INTROSPECTION = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    types {
      kind
      name
      fields {
        name
        args { name type { name kind ofType { name kind } } }
        type { name kind ofType { name kind } }
      }
    }
  }
}
"""
