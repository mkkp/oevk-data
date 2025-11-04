<!--
DOCUMENT METADATA
=================
Title: 004 Remove Duplicated Addresses
Type: Specification
Category: Feature
Status: Implemented
Version: 1.0
Created: 2024-10-01
Last Updated: 2024-10-15
Author: System
Change ID: 004

Related Documents:
- README.md

Related Code:
- src/etl/

Dependencies:
- DuckDB
- Polars

Keywords: change-specification, feature, implementation

Summary:
Change specification document for feature implementation.

Audience:
Developers, technical leads.
-->

Cleanup duplicated addresses in the source data.

Vármegye kód";"Vármegye";"OEVK";"Település kód";"Település";"TEVK";"Szavazókör";"Szavazókör cím";"Számlálásra kijelölt";"Akadálymentesített";"PIR";"Közterület név";"Közterület jelleg";"Házszám";"Épület";"Lépcsőház";"Kapukód";
"
"06";"Csongrád-Csanád";"01";"051";"Szeged";"09";"109";"Kodály tér 1. (SZTE Kossuth Zsuzsanna Technikum)";"N";"N";"6724";"Körtöltés";"utca";"000001";"D";"";"3326699";
"06";"Csongrád-Csanád";"01";"051";"Szeged";"09";"109";"Kodály tér 1. (SZTE Kossuth Zsuzsanna Technikum)";"N";"N";"6724";"Körtöltés";"utca";"000001";"E";"";"3334276";
"06";"Csongrád-Csanád";"01";"051";"Szeged";"09";"109";"Kodály tér 1. (SZTE Kossuth Zsuzsanna Technikum)";"N";"N";"6724";"Körtöltés";"utca";"000001";"";"D";"3333564";
"06";"Csongrád-Csanád";"01";"051";"Szeged";"09";"109";"Kodály tér 1. (SZTE Kossuth Zsuzsanna Technikum)";"N";"N";"6724";"Körtöltés";"utca";"000001";"";"E";"3337597";
"06";"Csongrád-Csanád";"01";"051";"Szeged";"09";"109";"Kodály tér 1. (SZTE Kossuth Zsuzsanna Technikum)";"N";"N";"6724";"Körtöltés";"utca";"000001";"";"";"6873793";
"06";"Csongrád-Csanád";"01";"051";"Szeged";"09";"109";"Kodály tér 1. (SZTE Kossuth Zsuzsanna Technikum)";"N";"N";"6724";"Körtöltés";"utca";"000001/D";"";"";"3329547";
"06";"Csongrád-Csanád";"01";"051";"Szeged";"09";"109";"Kodály tér 1. (SZTE Kossuth Zsuzsanna Technikum)";"N";"N";"6724";"Körtöltés";"utca";"000001/E";"";"";"3329305";
"06";"Csongrád-Csanád";"01";"051";"Szeged";"09";"109";"Kodály tér 1. (SZTE Kossuth Zsuzsanna Technikum)";"N";"N";"6724";"Körtöltés";"utca";"000001/F";"";"";"3348341";

There is duplicated addresses in the source data. For example, the address "Körtöltés utca 1/D", "Körtöltés utca 1/E",  appears multiple times with different combinations of house number, building, staircase, and gate code. This can lead to redundancy and inconsistencies in the transformed data. To address this, we need to implement a deduplication step in the transformation process. This step should identify and merge duplicate addresses based on a defined set of criteria, such as matching street name and house number, while considering variations in building, staircase, and gate code.

These addresses are same, the fullAddress is Körtöltés utca 1/D:
"06";"Csongrád-Csanád";"01";"051";"Szeged";"09";"109";"Kodály tér 1. (SZTE Kossuth Zsuzsanna Technikum)";"N";"N";"6724";"Körtöltés";"utca";"000001";"D";"";"3326699";
"06";"Csongrád-Csanád";"01";"051";"Szeged";"09";"109";"Kodály tér 1. (SZTE Kossuth Zsuzsanna Technikum)";"N";"N";"6724";"Körtöltés";"utca";"000001";"";"D";"3333564";
"06";"Csongrád-Csanád";"01";"051";"Szeged";"09";"109";"Kodály tér 1. (SZTE Kossuth Zsuzsanna Technikum)";"N";"N";"6724";"Körtöltés";"utca";"000001/D";"";"";"3329547";

These addresses are same, the fullAddress is Körtöltés utca 1/E:
"06";"Csongrád-Csanád";"01";"051";"Szeged";"09";"109";"Kodály tér 1. (SZTE Kossuth Zsuzsanna Technikum)";"N";"N";"6724";"Körtöltés";"utca";"000001";"";"E";"3337597";
"06";"Csongrád-Csanád";"01";"051";"Szeged";"09";"109";"Kodály tér 1. (SZTE Kossuth Zsuzsanna Technikum)";"N";"N";"6724";"Körtöltés";"utca";"000001";"E";"";"3334276";
"utca";"000001/E";"";"";"3329305";

The columns are:
Vármegye kód";"Vármegye";"OEVK";"Település kód";"Település";"TEVK";"Szavazókör";"Szavazókör cím";"Számlálásra kijelölt";"Akadálymentesített";"PIR";"Közterület név";"Közterület jelleg";"Házszám";"Épület";"Lépcsőház";"Kapukód";

Only care about Közterület név (Street Name), Közterület jelleg (Street Type), Házszám (House Number), Épület (Building), Lépcsőház (Staircase) to determine duplicated addresses.


For deduplication the following rules are applied:
When address has '/' in the house number, it is considered as a unique address.
When address does not have '/' in the house number, then the combination of house number, building, staircase is used to determine uniqueness.
When both building and staircase are empty, then only house number is used to determine uniqueness.
When either building or staircase is present, then the combination of house number, building, and staircase is used to determine uniqueness.

The full address format rules are:
 {Street Name} {Street type} {House Number}. {Building}. épület {Staircase}. lépcsőház

There are some special rules for formatting:
- If the house number contains a range (e.g., "000001-000005"), the range should be preserved in the formatted address (e.g., "1-5").
- If the house number contains a slash (e.g., "000001/D"), it should be preserved in the formatted address (e.g., "1/D").
- If the building is empty, it should be omitted from the formatted address.
- If the staircase is empty, it should be omitted from the formatted address.
- If both building and staircase are empty, only the street name, street type, and house number should be included in the formatted address.
- A period should be added after the house number.
- If building is present, it should be followed by ". épület".
- If staircase is present, it should be followed by ". lépcsőház".

Format example:
Input data:
"Street Name";"Street Type";"House Number";"Building";"Staircase"
"Körtöltés";"utca";"000001";"D";""
"Körtöltés";"utca";"000001";"";"D"
"Körtöltés";"utca";"000001";"D";"L"
"Körtöltés";"utca";"000001/D";"";""
"Körtöltés";"utca";"000001/D";"B";"L"
"Körtöltés";"utca";"000001/D";"";"L"
"Körtöltés";"utca";"000001-00005";"D";""
"Körtöltés";"utca";"000001-00005";"B";"L"


Output full address:
"Körtöltés utca 1/D."
"Körtöltés utca 1/D."
"Körtöltés utca 1/D. L. lépcsőház"
"Körtöltés utca 1/D."
"Körtöltés utca 1. B. épület L. lépcsőház"
"Körtöltés utca 1/D. L. lépcsőház"
"Körtöltés utca 1-5/D."
"Körtöltés utca 1-5. B. épület L. lépcsőház"



When building and staircase have leading zero, have to trim like as house number. When staircase is a number have to shown in full address as romanian number.

Input data:
"Street Name";"Street Type";"House Number";"Building";"Staircase"
"Berényi";"utca","000009","0001","0001"
"Berényi";"utca","000009","0001","0005"

Output full address:
Berényi utca 9. 1. épület I. lépcsőház
Berényi utca 9. 1. épület V. lépcsőház


The deduplicated data have to be exported partitioned by settlement code and settlement name, so it is easy to analyze the deduplication results per settlement. The deduplicated exports have to contains  The export file name have to be in the format of Address_{settlement_code}_{settlement_name}.csv, for example Address_051_Szeged.csv. The original address data have to be exported too, so it is easy to compare the deduplicated data with the original data. The export file name have to be in the format of OriginalAddress_{settlement_code}_{settlement_name}.csv, for example OriginalAddress_051_Szeged.csv

The deduplicated data have same structure as the original address data, but with deduplicated addresses.

The deduplication check the cleansed fullAddress and remove duplicates based on the rules above.

In the export for ID use UUID v3, which can be used the original id with 'oevk' namespace.
