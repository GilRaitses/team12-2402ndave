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

HUMAN_LOGIN = """
mutation Login($input: LoginInput!) {
  login(input: $input) {
    accessToken
    refreshToken
    user { id email firstName lastName }
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
      location { id locationName address city state }
      workOrderAssets {
        asset { id name status serialNumber }
      }
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
    city
    state
    zipcode
    parentId
    locationType
    locationTypeName
  }
}
"""

LOCATIONS_TREE = """
query FetchLocationsTree {
  locationsTree
}
"""

CREATE_WORK_ORDER = """
mutation CreateWorkOrder($input: CreateWorkOrderInput!) {
  createWorkOrder(input: $input) {
    id
    title
    description
    severity
    workOrderStage { name }
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
