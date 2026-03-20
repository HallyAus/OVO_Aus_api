"""GraphQL query definitions for OVO Energy Australia API."""

USAGE_V2_FRAGMENT = """
fragment UsageV2DataParts on UsageV2Data {
  solar {
    periodFrom
    periodTo
    consumption
    readType
    charge {
      value
      type
    }
  }
  export {
    periodFrom
    periodTo
    consumption
    readType
    charge {
      value
      type
    }
    rates {
      type
      charge {
        value
        type
      }
      consumption
      percentOfTotal
    }
  }
}
"""

GET_CONTACT_INFO = """
query GetContactInfo($input: GetContactInfoInput!) {
  GetContactInfo(input: $input) {
    accounts {
      id
      number
      customerId
      customerOrientatedBalance
      closed
      system
      hasSolar
      supplyAddress {
        buildingName
        buildingName2
        lotNumber
        flatType
        flatNumber
        floorType
        floorNumber
        houseNumber
        houseNumber2
        houseSuffix
        houseSuffix2
        streetSuffix
        streetName
        streetType
        suburb
        state
        postcode
        countryCode
        country
        addressType
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

GET_INTERVAL_DATA = f"""
query GetIntervalData($input: GetIntervalDataInput!) {{
  GetIntervalData(input: $input) {{
    daily {{
      ...UsageV2DataParts
    }}
    monthly {{
      ...UsageV2DataParts
    }}
    yearly {{
      ...UsageV2DataParts
    }}
  }}
}}

{USAGE_V2_FRAGMENT}
"""

GET_HOURLY_DATA = f"""
query GetHourlyData($input: GetHourlyDataInput!) {{
  GetHourlyData(input: $input) {{
    ...UsageV2DataParts
  }}
}}

{USAGE_V2_FRAGMENT}
"""

GET_PRODUCT_AGREEMENTS = """
query GetProductAgreements($input: GetAccountInfoInput!) {
  GetAccountInfo(input: $input) {
    id
    productAgreements {
      id
      fromDt
      toDt
      fixedContractToDt
      nmi
      product {
        code
        displayName
        paymentTiming
        standingChargeCentsPerDay
        isSolarSponge
        unitRatesCentsPerKWH {
          standard
          CL1
          CL2
          feedInTariff
          isPremiumFeedInTariff
          peak
          shoulder
          offPeak
          evOffPeak
          superOffPeak
          block {
            usageBlock1
            usageBlock2
            maxBlock1Threshold
            __typename
          }
          demand {
            highSeasonDemand
            lowSeasonDemand
            peakDemand
            __typename
          }
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
"""
