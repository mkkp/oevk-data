# Functional Requirements - OEVK Database

You are a business analyst. Analyze the requirements carefully. Think deeply about how to create the functional specification. Plan the implementation steps, entity models, data structures, data flows, and extraction logic to meet the requirements. The goal is to design a transformer program that fulfills the task definition.For diagrams use mermaid.

## Address Data

The address data will be structured based on the data found at

* [https://static.valasztas.hu/dyn/oevk_data/oevk.json](https://static.valasztas.hu/dyn/oevk_data/oevk.json) - 108 elements
* [https://static.valasztas.hu/dyn/oevk_data/Korzet_allomany_orszagos.zip](https://static.valasztas.hu/dyn/oevk_data/Korzet_allomany_orszagos.zip) - more than 3 million elements. A ZIP file containing 1 CSV file.


## Task

A software that downloads the address data and then loads it into the specified data structure.
The data should be loaded into a staging database, and then an export should be created for each table in CSV format. The address data should be stored in multiple CSV files, split by Settlement. The transformed database is packaged for release as `oevk.db` in compressed archives.


## Data Structure

From the given data, the following logical entities and the relationships between them can be established.
Where it was clear, the primary (PK - Primary Key) and foreign keys (FK - Foreign Key) have also been indicated.
The unique key is indicated by UC - Unique Constraint.


### Entities and Their Attributes

1. **County**
    * ID (PK): Unique identifier
    * CountyCode (UC): The unique identifier code of the county (e.g., "01")
    * CountyName: The name of the county (e.g., "Budapest")
2. **Settlement**
    * ID (PK): Unique identifier
    * SettlementCode (UC): The unique identifier code of the settlement (e.g., "001")
    * SettlementName: The name of the settlement (e.g., "Budapest I")
    * County_ID (FK): Link to the County entity.
3. **NationalIndividualElectoralDistrict (OEVK)**
    * ID (PK): Unique identifier
    * OEVK (UC): The code of the OEVK
    * Name: The name of the OEVK, concatenated from the SettlementName and the text "OEVK".
    * Center: The coordinates of the OEVK's center (from oevk.json).
    * Polygon: The polygon coordinates describing the OEVK (from oevk.json).
    * County_ID (FK): Link to the County entity.
4. **SettlementIndividualElectoralDistrict (TEVK)**
    * ID (PK): Unique identifier
    * TEVK: The code of the TEVK.
    * Name: The derived name of the TEVK.
    * County_ID (FK): Link to the County entity.
    * Settlement_ID (FK): Link to the Settlement entity.
    * NationalIndividualElectoralDistrict_ID (FK): Link to the NationalIndividualElectoralDistrict entity.
5. **PostalCode**
    * ID (PK): Unique identifier
    * PostalCode: The postal code (e.g., "1014").
6. **PostalCode_Settlement**
    * ID (PK): Unique identifier
    * PostalCode_ID (FK): Link to the PostalCode entity.
    * Settlement_ID (FK): Link to the Settlement entity.
7. **PollingStation**
    * ID (PK): Unique identifier
    * PollingStationAddress: The address of the polling station (e.g., "Úri utca 38. (Önkormányzat Intézménye)")
    * SettlementIndividualElectoralDistrict_ID (FK): Link to the SettlementIndividualElectoralDistrict entity.
    * County_ID (FK): Link to the County entity.
    * Settlement_ID (FK): Link to the Settlement entity.
    * NationalIndividualElectoralDistrict_ID (FK): Link to the NationalIndividualElectoralDistrict entity.
8. **PublicSpaceName**
    * ID (PK): Unique identifier (deterministic hash)
    * PublicSpaceName: The name of the public space (e.g., "Kossuth Lajos", "Petőfi Sándor")
    
9. **PublicSpaceType**
    * ID (PK): Unique identifier (deterministic hash)
    * PublicSpaceType: The type of the public space (e.g., "utca", "tér", "út", "köz")
    
10. **SettlementPublicSpaces**
    * ID (PK): Unique identifier (deterministic hash)
    * Settlement_ID (FK): Link to the Settlement entity
    * PublicSpaceName_ID (FK): Link to the PublicSpaceName entity
    * PublicSpaceType_ID (FK): Link to the PublicSpaceType entity
    
11. **Address**
    * ID (PK): Unique identifier
    * Sequence: For example, the loading sequence.
    * FullAddress: The full address, concatenated from multiple fields.
    * PublicSpaceName_ID (FK): Link to the PublicSpaceName entity
    * PublicSpaceType_ID (FK): Link to the PublicSpaceType entity
    * HouseNumber: The house number.
    * Building: The building letter/number.
    * Staircase: The staircase letter/number.
    * Sequence: The serial number indicating the loading order.
    * PIR (FK): Link to the PostalCode entity.
    * PollingStation_ID (FK): Link to the PollingStation entity.
    * SettlementIndividualElectoralDistrict_ID (FK): Link to the SettlementIndividualElectoralDistrict entity.
    * PostalCode_ID (FK): Link to the PostalCode entity.
    * County_ID (FK): Link to the County entity.
    * Settlement_ID (FK): Link to the Settlement entity.
    * NationalIndividualElectoralDistrict_ID (FK): Link to the NationalIndividualElectoralDistrict entity.

12. **CanonicalAddress**
    * ID (PK): Unique identifier (deterministic hash)
    * CountyCode: The county code
    * SettlementName: The settlement name
    * StreetName: The street name
    * HouseNumber: The house number
    * AccessibilityFlag: Accessibility flag

13. **AddressMapping**
    * ID (PK): Unique identifier
    * OriginalAddress_ID (FK): Link to the original Address entity
    * CanonicalAddress_ID (FK): Link to the CanonicalAddress entity

14. **AddressPollingStations**
    * ID (PK): Unique identifier
    * CanonicalAddress_ID (FK): Link to the CanonicalAddress entity
    * PollingStation_ID (FK): Link to the PollingStation entity

15. **AddressPIRCodes**
    * ID (PK): Unique identifier
    * CanonicalAddress_ID (FK): Link to the CanonicalAddress entity
    * PIRCode: The PIR code

16. **DeduplicationReport**
    * ID (PK): Unique identifier (deterministic hash)
    * RunID: Unique run identifier
    * TotalAddresses: Total number of addresses processed
    * DuplicatesFound: Number of duplicate addresses found
    * CanonicalAddressesCreated: Number of canonical addresses created
    * ProcessingTimeMS: Processing time in milliseconds
    * Status: Processing status (completed/failed)
    * ErrorMessage: Error message if failed
    * CreatedAt: Report creation timestamp

#### Relationships

* **County** 1--* **Settlement**: One county can have multiple settlements, but one settlement belongs to only one county.
* **County** 1--* **NationalIndividualElectoralDistrict**: One county can contain multiple OEVKs.
* **Settlement** 1--* **SettlementIndividualElectoralDistrict**: One settlement can contain multiple TEVKs.
* **Settlement** *--* **PostalCode**: An n-to-m relationship; a settlement can have multiple postal codes, and a postal code can cover multiple settlements (although this is rare in practice). The relationship is managed through the **PostalCode_Settlement** junction table.
* **SettlementIndividualElectoralDistrict** 1--* **PollingStation**: One TEVK can have multiple polling stations.
* **PollingStation** 1--* **Address**: One polling station serves multiple addresses.
* **Settlement** *--* **PublicSpaceName**: A settlement can have multiple public space names, and a public space name can appear in multiple settlements. The relationship is managed through the **SettlementPublicSpaces** junction table.
* **Settlement** *--* **PublicSpaceType**: A settlement can have multiple public space types, and a public space type can appear in multiple settlements. The relationship is managed through the **SettlementPublicSpaces** junction table.
* **PublicSpaceName** *--* **PublicSpaceType**: A public space name can have multiple types, and a public space type can be used by multiple names. The relationship is managed through the **SettlementPublicSpaces** junction table.

#### Pseudocode for Derived Fields

##### NationalIndividualElectoralDistrict.Name:
```
SET Name = Settlement.SettlementName + " " + OEVK
```

##### SettlementIndividualElectoralDistrict.Name:
```
IF CSV.TEVK IS NOT EMPTY AND CSV.TEVK IS NOT NULL THEN
    SET Name = Settlement.SettlementName + " " + CSV.TEVK
ELSE
    SET Name = Settlement.SettlementName
END IF
```

##### Address.FullAddress:
```
DEFINE FUNCTION Concatenate(fields)
    SET Result = ""
    FOR EACH Field IN fields
        IF Field IS NOT EMPTY AND Field IS NOT NULL THEN
            IF Result IS NOT EMPTY THEN
                SET Result = Result + " "
            END IF
            SET Result = Result + Field
        END IF
    END FOR
    RETURN Result
END FUNCTION

SET FullAddress = Concatenate([CSV.PublicSpaceName, CSV.PublicSpaceType, CSV.HouseNumber, CSV.Building, CSV.Staircase])
```

#### Unified Entity-Relationship Diagram

The following diagram shows all entities and the relationships between them.

``` mermaid
erDiagram
    County {
        int ID PK "Unique identifier"
        string CountyCode "The unique identifier code of the county"
        string CountyName "The name of the county"
    }

    Settlement {
        int ID PK "Unique identifier"
        string SettlementCode "The unique identifier code of the settlement"
        string SettlementName "The name of the settlement"
        int County_ID FK "Link to the County entity"
    }

    NationalIndividualElectoralDistrict {
        int ID PK "Unique identifier"
        string OEVK "The code of the OEVK"
        string Name "The derived name of the OEVK"
        string Center "The coordinates of the OEVK's center"
        string Polygon "The polygon coordinates describing the OEVK"
        int County_ID FK "Link to the County entity"
    }

    SettlementIndividualElectoralDistrict {
        int ID PK "Unique identifier"
        string TEVK "The code of the TEVK"
        string Name "The derived name of the TEVK"
        int County_ID FK "Link to the County entity"
        int Settlement_ID FK "Link to the Settlement entity"
        int NationalIndividualElectoralDistrict_ID FK "Link to the OEVK entity"
    }

    PostalCode {
        int ID PK "Unique identifier"
        string PostalCode "The postal code"
    }

    PostalCode_Settlement {
        int ID PK "Unique identifier"
        int PostalCode_ID FK "Link to the PostalCode entity"
        int Settlement_ID FK "Link to the Settlement entity"
    }

    PollingStation {
        int ID PK "Unique identifier"
        string PollingStationAddress "The address of the polling station"
        int SettlementIndividualElectoralDistrict_ID FK "Link to the TEVK entity"
        int County_ID FK "Link to the County entity"
        int Settlement_ID FK "Link to the Settlement entity"
        int NationalIndividualElectoralDistrict_ID FK "Link to the OEVK entity"
    }

    PublicSpaceName {
        int ID PK "Unique identifier (deterministic hash)"
        string PublicSpaceName "The name of the public space"
    }

    PublicSpaceType {
        int ID PK "Unique identifier (deterministic hash)"
        string PublicSpaceType "The type of the public space"
    }

    SettlementPublicSpaces {
        int ID PK "Unique identifier (deterministic hash)"
        int Settlement_ID FK "Link to the Settlement entity"
        int PublicSpaceName_ID FK "Link to the PublicSpaceName entity"
        int PublicSpaceType_ID FK "Link to the PublicSpaceType entity"
    }

    Address {
        int ID PK "Unique identifier"
        string FullAddress "The full address, concatenated from multiple fields"
        int PublicSpaceName_ID FK "Link to the PublicSpaceName entity"
        int PublicSpaceType_ID FK "Link to the PublicSpaceType entity"
        string HouseNumber "The house number"
        string Building "The building letter"
        string Staircase "The staircase letter"
        int Sequence "The serial number indicating the loading order"
        int PostalCode_ID FK "Link to the PostalCode entity (PIR)"
        int PollingStation_ID FK "Link to the PollingStation entity"
        int SettlementIndividualElectoralDistrict_ID FK "Link to the TEVK entity"
        int County_ID FK "Link to the County entity"
        int Settlement_ID FK "Link to the Settlement entity"
        int NationalIndividualElectoralDistrict_ID FK "Link to the OEVK entity"
    }

    CanonicalAddress {
        int ID PK "Unique identifier (deterministic hash)"
        string CountyCode "The county code"
        string SettlementName "The settlement name"
        string StreetName "The street name"
        string HouseNumber "The house number"
        string AccessibilityFlag "Accessibility flag"
    }

    AddressMapping {
        int ID PK "Unique identifier"
        int OriginalAddress_ID FK "Link to the original Address entity"
        int CanonicalAddress_ID FK "Link to the CanonicalAddress entity"
    }

    AddressPollingStations {
        int ID PK "Unique identifier"
        int CanonicalAddress_ID FK "Link to the CanonicalAddress entity"
        int PollingStation_ID FK "Link to the PollingStation entity"
    }

    AddressPIRCodes {
        int ID PK "Unique identifier"
        int CanonicalAddress_ID FK "Link to the CanonicalAddress entity"
        string PIRCode "The PIR code"
    }

    DeduplicationReport {
        int ID PK "Unique identifier (deterministic hash)"
        string RunID "Unique run identifier"
        int TotalAddresses "Total number of addresses processed"
        int DuplicatesFound "Number of duplicate addresses found"
        int CanonicalAddressesCreated "Number of canonical addresses created"
        int ProcessingTimeMS "Processing time in milliseconds"
        string Status "Processing status (completed/failed)"
        string ErrorMessage "Error message if failed"
        datetime CreatedAt "Report creation timestamp"
    }

    County ||--o{ Settlement : "contains"
    County ||--o{ NationalIndividualElectoralDistrict : "contains"
    Settlement ||--o{ SettlementIndividualElectoralDistrict : "contains"
    Settlement }o--o{ PostalCode_Settlement : "n-m relationship"
    PostalCode }o--o{ PostalCode_Settlement : "n-m relationship"
    NationalIndividualElectoralDistrict ||--o{ SettlementIndividualElectoralDistrict : "contains"
    SettlementIndividualElectoralDistrict ||--o{ PollingStation : "contains"
    PollingStation ||--o{ Address : "contains"
    Settlement }o--o{ SettlementPublicSpaces : "n-m relationship"
    PublicSpaceName }o--o{ SettlementPublicSpaces : "n-m relationship"
    PublicSpaceType }o--o{ SettlementPublicSpaces : "n-m relationship"

    %% Redundant but specified relationships for clarity

    County ||..o{ Address : "references"
    Settlement ||..o{ Address : "references"
    NationalIndividualElectoralDistrict ||..o{ Address : "references"
    SettlementIndividualElectoralDistrict ||..o{ Address : "references"
    PostalCode ||..o{ Address : "references"
    PublicSpaceName ||..o{ Address : "references"
    PublicSpaceType ||..o{ Address : "references"
    County ||..o{ PollingStation : "references"
    Settlement ||..o{ PollingStation : "references"
    NationalIndividualElectoralDistrict ||..o{ PollingStation : "references"

    %% Deduplication relationships
    Address ||--o{ AddressMapping : "maps to"
    CanonicalAddress ||--o{ AddressMapping : "maps from"
    CanonicalAddress ||--o{ AddressPollingStations : "assigned to"
    PollingStation ||--o{ AddressPollingStations : "serves"
    CanonicalAddress ||--o{ AddressPIRCodes : "has"
    DeduplicationReport ||--|| CanonicalAddress : "reports on"

```
## Data samples

### Sample: oevk.sample.json:

``` json
[
  {
    "maz": "01",
    "evk": "01",
    "centrum": "47.490980 19.045150",
    "poligon": "47.5146939015652 19.0436777064605,47.5147366015652 19.0434745064606,47.5147466015652 19.0433207064606,47.5147097015653 19.0420223064607,47.5119922015653 19.0426256064606,47.5115985015653 19.0427130064606,47.5077016015654 19.0423588064605,47.5076813015657"
  },
  {
    "maz": "01",
    "evk": "02",
    "centrum": "47.485101 19.080764",
    "poligon": "47.4996322137724 19.0974788152747,47.4996255813479 19.0968917128433,47.4996085648716 19.095362998549,47.4996034367106 19.0937052624424,47.499605052972 19.0917937498923,47.4996201737211 19.0895920256723,47.4996355425225 19.0882400144191,47.499607479491 19.0865477577971,47.4996065784791 19.0818372128148,47.4995209015618"
   }, {
       "maz": "19",
       "evk": "03",
       "centrum": "46.914930 17.458070",
       "poligon": "46.9608704 17.2482257,46.9567081 17.2500314,46.9546216 17.2384229,46.9474434 17.2419966,46.9474258 17.2408838,46.9451571 17.2420737,46.9447553 17.2409739,46.9447379 17.2398702,46.9428357 17.2399344,46.9420559 17.2388475,46.9420206 17.2366221,46.941625 17.2355222,46.9412409 17.2355352,46.9412144 17.2338707,46.9404496 17.2333355,46.9400654 17.2333485,46.9350883 17.2318519,46.9350441 17.2290751,46.9331419 17.2291397,46.9319929 17.2286177,46.9319841 17.228066,46.9312043 17.2269794,46.9311955 17.2264277,46.9308085 17.2258798,46.9304244 17.2258929,46.9296712 17.2264795,46.9292933 17.2264924,46.9281558 17.227083,46.9277866 17.2276475,46.9270245 17.2276734,46.9258934 17.2282729,46.9239912 17.2283375,46.9232379 17.228915,46.9232468 17.2294756,46.9228714 17.2300403,46.9213534 17.2300918,46.9213623 17.2306525,46.9206002 17.2306783,46.9202248 17.2410589,46.9722108 17.2428363,46.9699832 17.246244,46.9684414 17.245182,46.9672689 17.2435553,46.9665393 17.2452461,46.9661639 17.2458202,46.9608704 17.2482257"
   }, {
       "maz": "20",
       "evk": "03",
       "centrum": "46.499570 16.809120",
       "poligon": "46.5620599 16.5281581,46.5620477 16.5276103,46.5612858 16.527646,46.5612612 16.5265414,46.5619985 16.5254012,46.5619864 16.5248534,46.5623458 16.5237309,46.5653874 16.5235885,46.5653628 16.5224838,46.5645886 16.5219717,46.5649481 16.5208491,46.5641861 16.5208848,46.5630217 16.5198336,46.5622351 16.5187648,46.561851 16.5187828,46.5614978 16.5345549,46.56751 16.5334326,46.5674976 16.5328757,46.5663456 16.5323811,46.5659432 16.531294,46.5659065 16.5296416,46.5654979 16.5285549,46.5651077 16.5280157,46.5635716 16.5275391,46.5620599 16.5281581"
   }
]
```

### Samlple: Korzet_levalogatas20250702__ORSZAGOS.sample.csv:

``` csv
"Vármegye kód";"Vármegye";"OEVK";"Település kód";"Település";"TEVK";"Szavazókör";"Szavazókör cím";"Számlálásra kijelölt";"Akadálymentesített";"PIR";"Közterület név";"Közterület jelleg";"Házszám";"Épület";"Lépcsőház";"Kapukód";
"01";"Budapest";"01";"001";"Budapest I";"01";"001";"Úri utca 38. (Önkormányzat Intézménye)";"N";"I";"1014";"Anna";"utca";"000001";"";"";"249649";
"01";"Budapest";"01";"001";"Budapest I";"01";"001";"Úri utca 38. (Önkormányzat Intézménye)";"N";"I";"1014";"Balta";"köz";"000001";"";"";"1352512";
"01";"Budapest";"01";"001";"Budapest I";"01";"001";"Úri utca 38. (Önkormányzat Intézménye)";"N";"I";"1014";"Balta";"köz";"000004";"";"";"296";
"01";"Budapest";"04";"002";"Budapest II";"02";"060";"Marczibányi tér 1. (Kodály Z. Ált. Isk. és Gimn.)";"N";"N";"1024";"Retek";"utca";"000004";"";"";"250233";
"01";"Budapest";"04";"002";"Budapest II";"02";"060";"Marczibányi tér 1. (Kodály Z. Ált. Isk. és Gimn.)";"N";"N";"1024";"Retek";"utca";"000005";"";"";"1459";
"01";"Budapest";"04";"002";"Budapest II";"02";"060";"Marczibányi tér 1. (Kodály Z. Ált. Isk. és Gimn.)";"N";"N";"1024";"Retek";"utca";"000006";"";"";"1460";
"01";"Budapest";"04";"002";"Budapest II";"02";"060";"Marczibányi tér 1. (Kodály Z. Ált. Isk. és Gimn.)";"N";"N";"1024";"Retek";"utca";"000008";"";"";"1461";
"01";"Budapest";"04";"002";"Budapest II";"02";"060";"Marczibányi tér 1. (Kodály Z. Ált. Isk. és Gimn.)";"N";"N";"1024";"Retek";"utca";"000010";"";"";"1463";
"01";"Budapest";"04";"002";"Budapest II";"02";"060";"Marczibányi tér 1. (Kodály Z. Ált. Isk. és Gimn.)";"N";"N";"1024";"Retek";"utca";"000012";"";"";"1464";
"01";"Budapest";"04";"002";"Budapest II";"02";"060";"Marczibányi tér 1. (Kodály Z. Ált. Isk. és Gimn.)";"N";"N";"1024";"Retek";"utca";"000014";"";"";"1465";
"01";"Budapest";"04";"002";"Budapest II";"05";"002";"Lajos u. 1-5. (Than Károly Gimn.)";"N";"N";"1023";"Diófa";"lejtő";"000002";"";"";"7481042";
"01";"Budapest";"04";"002";"Budapest II";"05";"002";"Lajos u. 1-5. (Than Károly Gimn.)";"N";"N";"1023";"Diófa";"lejtő";"000003";"";"";"7589525";
"01";"Budapest";"04";"002";"Budapest II";"05";"002";"Lajos u. 1-5. (Than Károly Gimn.)";"N";"N";"1023";"Frankel Leó";"út";"000055-0057";"";"A";"7433691";
"01";"Budapest";"04";"002";"Budapest II";"05";"002";"Lajos u. 1-5. (Than Károly Gimn.)";"N";"N";"1023";"Frankel Leó";"út";"000055-0057";"";"B";"7433690";
"01";"Budapest";"04";"002";"Budapest II";"06";"018";"Törökvész út 67. (Ált. Isk.)";"N";"N";"1025";"Törökvész";"út";"000041";"";"";"1833";
"01";"Budapest";"04";"002";"Budapest II";"06";"018";"Törökvész út 67. (Ált. Isk.)";"N";"N";"1025";"Törökvész";"út";"000043";"";"";"2872743";
"01";"Budapest";"04";"002";"Budapest II";"06";"018";"Törökvész út 67. (Ált. Isk.)";"N";"N";"1025";"Törökvész";"út";"000045";"";"";"668874";
"01";"Budapest";"04";"002";"Budapest II";"06";"018";"Törökvész út 67. (Ált. Isk.)";"N";"N";"1025";"Törökvész";"út";"000047";"";"";"2239667";
"01";"Budapest";"04";"002";"Budapest II";"06";"018";"Törökvész út 67. (Ált. Isk.)";"N";"N";"1025";"Törökvész";"út";"000047/A";"";"";"1352694";
"01";"Budapest";"04";"002";"Budapest II";"06";"018";"Törökvész út 67. (Ált. Isk.)";"N";"N";"1025";"Törökvész";"út";"000047/B";"";"";"1428438";
"01";"Budapest";"04";"002";"Budapest II";"06";"018";"Törökvész út 67. (Ált. Isk.)";"N";"N";"1025";"Törökvész";"út";"000049-0055";"A";"";"843916";
"01";"Budapest";"04";"002";"Budapest II";"06";"018";"Törökvész út 67. (Ált. Isk.)";"N";"N";"1025";"Törökvész";"út";"000049-0055";"B";"";"7412979";
"01";"Budapest";"04";"002";"Budapest II";"06";"018";"Törökvész út 67. (Ált. Isk.)";"N";"N";"1025";"Törökvész";"út";"000049-0055";"C";"";"7412980";
"01";"Budapest";"04";"002";"Budapest II";"06";"018";"Törökvész út 67. (Ált. Isk.)";"N";"N";"1025";"Törökvész";"út";"000049-0055";"G";"";"7412981";
"01";"Budapest";"04";"002";"Budapest II";"06";"018";"Törökvész út 67. (Ált. Isk.)";"N";"N";"1025";"Törökvész";"út";"000049-0055";"H";"";"7412982";
"01";"Budapest";"04";"002";"Budapest II";"06";"018";"Törökvész út 67. (Ált. Isk.)";"N";"N";"1025";"Törökvész";"út";"000057";"A";"";"7484473";
"01";"Budapest";"04";"002";"Budapest II";"06";"018";"Törökvész út 67. (Ált. Isk.)";"N";"N";"1025";"Törökvész";"út";"000057";"B";"";"843921";
"01";"Budapest";"16";"020";"Budapest XX";"08";"045";"Lázár u. 20. (Iskola)";"N";"N";"1202";"Csallóköz";"utca";"000003";"";"";"268789";
"01";"Budapest";"16";"020";"Budapest XX";"08";"045";"Lázár u. 20. (Iskola)";"N";"N";"1202";"Csallóköz";"utca";"000004";"";"";"1232624";
"01";"Budapest";"16";"020";"Budapest XX";"08";"045";"Lázár u. 20. (Iskola)";"N";"N";"1202";"Csallóköz";"utca";"000005";"";"";"1435187";
"01";"Budapest";"16";"020";"Budapest XX";"08";"045";"Lázár u. 20. (Iskola)";"N";"N";"1202";"Csallóköz";"utca";"000006";"";"";"31650";
"01";"Budapest";"16";"020";"Budapest XX";"08";"045";"Lázár u. 20. (Iskola)";"N";"N";"1202";"Csallóköz";"utca";"000007";"";"";"1435188";
"01";"Budapest";"16";"020";"Budapest XX";"08";"045";"Lázár u. 20. (Iskola)";"N";"N";"1202";"Csallóköz";"utca";"000008";"";"";"989178";
"03";"Bács-Kiskun";"02";"060";"Kecskemét";"14";"092";"Katona Zsigmond utca 1. (Mathiász János Ált. Isk.)";"N";"I";"6000";"Katonatelep";"tanya";"014862";"";"";"3491222";
"03";"Bács-Kiskun";"02";"060";"Kecskemét";"14";"092";"Katona Zsigmond utca 1. (Mathiász János Ált. Isk.)";"N";"I";"6000";"Katonatelep";"tanya";"014866";"";"";"3444606";
"03";"Bács-Kiskun";"02";"060";"Kecskemét";"14";"092";"Katona Zsigmond utca 1. (Mathiász János Ált. Isk.)";"N";"I";"6000";"Katonatelep";"tanya";"014881";"";"";"2829104";
"03";"Bács-Kiskun";"02";"060";"Kecskemét";"14";"092";"Katona Zsigmond utca 1. (Mathiász János Ált. Isk.)";"N";"I";"6000";"Katonatelep";"tanya";"014884";"";"";"2912900";
"20";"Zala";"02";"258";"Tekenye";"";"001";"Hunyadi u. 11. (Kultúrház)";"N";"I";"8793";"Tölgyvári";"utca";"000035";"";"";"1760244";
"20";"Zala";"02";"258";"Tekenye";"";"001";"Hunyadi u. 11. (Kultúrház)";"N";"I";"8793";"Tölgyvári";"utca";"000037";"";"";"1118236";
"20";"Zala";"02";"258";"Tekenye";"";"001";"Hunyadi u. 11. (Kultúrház)";"N";"I";"8793";"Tölgyvári";"utca";"000039";"";"";"2554545";
"20";"Zala";"02";"258";"Tekenye";"";"001";"Hunyadi u. 11. (Kultúrház)";"N";"I";"8793";"Tölgyvári";"utca";"000041";"";"";"1876043";
"20";"Zala";"02";"258";"Tekenye";"";"001";"Hunyadi u. 11. (Kultúrház)";"N";"I";"8793";"Tölgyvári";"utca";"000043";"";"";"3403909";
"20";"Zala";"02";"258";"Tekenye";"";"001";"Hunyadi u. 11. (Kultúrház)";"N";"I";"8793";"Tölvár";"";"000045/0029";"";"";"2882857";
"20";"Zala";"02";"258";"Tekenye";"";"001";"Hunyadi u. 11. (Kultúrház)";"N";"I";"8793";"Tölvár";"";"031287";"";"";"4400534";
```

## Table of Translations

The following table contains the translations for the Hungarian names and identifiers used in the document.

| Hungarian Name                         | English Translation                  |
|---------------------------------------|--------------------------------------|
| **Entities**                          |                                      |
| Varmegye                               | County                               |
| Telepules                              | Settlement                           |
| OrszagosEgyeniValasztokerulet (OEVK)  | NationalIndividualElectoralDistrict  |
| TelepulesiEgyeniValasztokerulet (TEVK)| SettlementIndividualElectoralDistrict|
| Iranyitoszam                           | PostalCode                           |
| Iranyitoszam_Telepules                 | PostalCode_Settlement                |
| Szavazokor                             | PollingStation                       |
| Cim                                    | Address                              |
| KozteruletNev                          | PublicSpaceName                      |
| KozteruletJelleg                       | PublicSpaceType                      |
| Telepules_Kozteruletek                 | SettlementPublicSpaces               |
| **Attributes & General Terms**         |                                      |
| Azonosító                              | Identifier                           |
| Kód                                    | Code                                 |
| Név                                    | Name                                 |
| VarmegyeKod                            | CountyCode                           |
| VarmegyeNev                            | CountyName                           |
| TelepulesKod                           | SettlementCode                       |
| TelepulesNev                           | SettlementName                       |
| Centrum                                | Center                               |
| Poligon                                | Polygon                              |
| Iranyitoszam                           | PostalCode                           |
| SzavazokorCim                          | PollingStationAddress                 |
| Sorrend                                | Order / Sequence                      |
| TeljesCim                              | FullAddress                          |
| KozteruletNev                          | PublicSpaceName                       |
| KozteruletJelleg                       | PublicSpaceType                       |
| Hazszam                                | HouseNumber                          |
| Epulet                                 | Building                             |
| Lepcsohaz                              | Staircase                            |
| Elsődleges kulcs (PK)                  | Primary Key (PK)                      |
| Idegen kulcs (FK)                      | Foreign Key (FK)                      |
| Egyedi kulcs (UC)                      | Unique Constraint (UC)                |
