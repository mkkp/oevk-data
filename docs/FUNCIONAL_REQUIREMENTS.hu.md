
# Funkcionális követelmények - OEVK adatbazis


## Cimadatok

Az cimadatok a [https://vtr.valasztas.hu/stat?tab=letoltesek](https://vtr.valasztas.hu/stat?tab=letoltesek) -n talalhato adatok alapjan kerulnek kialakitasra.

[https://static.valasztas.hu/dyn/oevk_data/oevk.json](https://static.valasztas.hu/dyn/oevk_data/oevk.json) - 108 elem

[https://static.valasztas.hu/dyn/oevk_data/Korzet_allomany_orszagos.zip](https://static.valasztas.hu/dyn/oevk_data/Korzet_allomany_orszagos.zip) több, mint 3 millió elem. ZIP file, amely 1 CSV filet tartalmaz.


## Feladat

Olyan python szoftvert kesziteni, amely letolti a cimadatokat, majd a megadott adatszerkezetbe tolti. Az adaokat sqlite adatbazisba toltse be, majd
tablankent keszitsen exportot CSV formaban. A cim adatok tobb CSV fileba keruljenek tarolasra.

### Adatszerkezet

A megadott adatokból az alábbi logikai entitásokat és a köztük lévő kapcsolatokat lehet kialakítani. Ahol egyértelmű volt, ott jelöltem az elsődleges (PK - Primary Key) és idegen kulcsokat (FK - Foreign Key) is. Az egyedi kulcsot az UC - Unique Constraint jelzi.


#### Entitások és Attribútumaik


1. **Varmegye**
    * ID (PK): Egyedi azonositó
    * VarmegyeKod (UC): A vármegye egyedi azonosító kódja. (pl. "01")
    * VarmegyeNev: A vármegye neve. (pl. "Budapest")
2. **Telepules**
    * ID (PK): Egyedi azonositó
    * TelepulesKod (UC): A település egyedi azonosító kódja. (pl. "001")
    * TelepulesNev: A település neve. (pl. "Budapest I")
    * Varmegye_ID (FK): Kapcsolat a Varmegye entitáshoz.
3. **OrszagosEgyeniValasztokerulet (OEVK)**
    * ID (PK): Egyedi azonositó
    * OEVK (UC): Az OEVK kodja
    * Nev: Az OEVK neve, a TelepulesNev és az "OEVK" szöveg összefűzéséből.
    * Centrum: Az OEVK centrumának koordinátái (a oevk.json-ból).
    * Poligon: Az OEVK-t leíró poligon koordinátái (a oevk.json-ból).
    * Varmegye_ID (FK): Kapcsolat a Varmegye entitáshoz.
4. **TelepulesiEgyeniValasztokerulet (TEVK)**
    * ID (PK): Egyedi azonositó
    * TEVK A TEVK kódja.
    * Nev: A TEVK származtatott neve.
    * Varmegye_ID (FK): Kapcsolat a Varmegye entitáshoz.
    * Telepules_ID  (FK): Kapcsolat a Telepules entitáshoz.
    * OrszagosEgyeniValasztokerulet_ID (FK): Kapcsolat a OrszagosEgyeniValasztokerulet entitáshoz.
5. **Iranyitoszam**
    * ID (PK): Egyedi azonositó
    * Iranyitoszam: Az irányítószám. (pl. "1014")
6. **Iranyitoszam_Telepules**
    * ID (PK): Egyedi azonositó
    * Iranyitoszam_ID  (FK): Kapcsolat a Iranyitoszam entitáshoz
    * Telepules_ID (FK): Kapcsolat a Telepules entitáshoz
7. **Szavazokor**
    * ID (PK): Egyedi azonositó
    * SzavazokorCim: A szavazókör címe. (pl. "Úri utca 38. (Önkormányzat Intézménye)")
    * TelepulesiEgyeniValasztokerulet_ID (FK): Kapcsolat a TelepulesiEgyeniValasztokerulet entitáshoz.
    * Varmegye_ID (FK): Kapcsolat a Varmegye entitáshoz.
    * Telepules_ID  (FK): Kapcsolat a Telepules entitáshoz.
    * OrszagosEgyeniValasztokerulet_ID (FK): Kapcsolat a OrszagosEgyeniValasztokerulet entitáshoz.
8. **Cim**
    * ID (PK): Egyedi azonositó
    * Sorrend: Például a betöltési Sorrend.
    * TeljesCim: A teljes cím, több mezőből összefűzve.
    * KozteruletNev: A közterület neve.
    * KozteruletJelleg: A közterület jellege.
    * Hazszam: A házszám.
    * Epulet: Az épület jele.
    * Lepcsohaz: A lépcsőház jele.
    * Sorrend: A betöltési sorrendet jelző sorszám.
    * PIR (FK): Kapcsolat az Iranyitoszam entitáshoz.
    * Szavazokor_ID (FK): Kapcsolat a Szavazokor entitáshoz.
    * TelepulesiEgyeniValasztokerulet_ID (FK): Kapcsolat a TelepulesiEgyeniValasztokerulet entitáshoz.
    * Iranyitoszam_ID  (FK): Kapcsolat a Iranyitoszam entitáshoz
    * Varmegye_ID (FK): Kapcsolat a Varmegye entitáshoz.
    * Telepules_ID  (FK): Kapcsolat a Telepules entitáshoz.
    * OrszagosEgyeniValasztokerulet_ID (FK): Kapcsolat a OrszagosEgyeniValasztokerulet entitáshoz.


#### Kapcsolatok



* **Varmegye** 1--* **Telepules**: Egy vármegyéhez több település tartozhat, de egy település csak egy vármegyéhez.
* **Varmegye** 1--* **OrszagosEgyeniValasztokerulet**: Egy vármegyéhez több OEVK tartozhat.
* **Telepules** 1--* **TelepulesiEgyeniValasztokerulet**: Egy településhez több TEVK tartozhat.
* **Telepules** *--* **Iranyitoszam**: n..m kapcsolat, egy településnek több irányítószáma is lehet, és egy irányítószám több települést is lefedhet (bár a gyakorlatban ez ritkább). A kapcsolatot a **Iranyitoszam_Telepules **kapcsolótáblán keresztül történik.
* **TelepulesiEgyeniValasztokerulet** 1--* **Szavazokor**: Egy TEVK-hez több szavazókör tartozhat.
* **Szavazokor** 1--* **Cim**: Egy szavazókörhöz több cím tartozik.


#### Pszeudokód a Származtatott Mezőkhöz


##### OrszagosEgyeniValasztokerulet.Nev:
```
SET Nev = Telepules.TelepulesNev + " " + OEVK \
```


##### TelepulesiEgyeniValasztokerulet.Nev:
```
IF CSV.TEVK IS NOT EMPTY AND CSV.TEVK IS NOT NULL THEN \
    SET Nev = Telepules.TelepulesNev + " " + CSV.TEVK \
ELSE \
    SET Nev = Telepules.TelepulesNev \
END IF \
```

##### Cim.TeljesCim:

```
DEFINE FUNCTION Láncol(mezők) \
    SET Eredmény = "" \
    FOR EACH Mező IN mezők \
        IF Mező IS NOT EMPTY AND Mező IS NOT NULL THEN \
            IF Eredmény IS NOT EMPTY THEN \
                SET Eredmény = Eredmény + " " \
            END IF \
            SET Eredmény = Eredmény + Mező \
        END IF \
    END FOR \
    RETURN Eredmény \
END FUNCTION \
 \
SET TeljesCim = Láncol([CSV.Közterület név, CSV.Közterület jelleg, CSV.Házszám, CSV.Épület, CSV.Lépcsőház]) \
```

#### Egyesített Entitás-Kapcsolati Diagram

Az alábbi diagram bemutatja az összes entitást és a köztük lévő kapcsolatokat.

``` mermaid
erDiagram
    Varmegye {
        int ID PK "Egyedi azonosító"
        string VarmegyeKod "A vármegye egyedi azonosító kódja"
        string VarmegyeNev "A vármegye neve"
    }

    Telepules {
        int ID PK "Egyedi azonosító"
        string TelepulesKod "A település egyedi azonosító kódja"
        string TelepulesNev "A település neve"
        int Varmegye_ID FK "Kapcsolat a Varmegye entitáshoz"
    }

    OrszagosEgyeniValasztokerulet {
        int ID PK "Egyedi azonosító"
        string OEVK "Az OEVK kódja"
        string Nev "Az OEVK származtatott neve"
        string Centrum "Az OEVK centrumának koordinátái"
        string Poligon "Az OEVK-t leíró poligon koordinátái"
        int Varmegye_ID FK "Kapcsolat a Varmegye entitáshoz"
    }

    TelepulesiEgyeniValasztokerulet {
        int ID PK "Egyedi azonosító"
        string TEVK "A TEVK kódja"
        string Nev "A TEVK származtatott neve"
        int Varmegye_ID FK "Kapcsolat a Varmegye entitáshoz"
        int Telepules_ID FK "Kapcsolat a Telepules entitáshoz"
        int OrszagosEgyeniValasztokerulet_ID FK "Kapcsolat az OEVK entitáshoz"
    }

    Iranyitoszam {
        int ID PK "Egyedi azonosító"
        string Iranyitoszam "Az irányítószám"
    }

    Iranyitoszam_Telepules {
        int ID PK "Egyedi azonosító"
        int Iranyitoszam_ID FK "Kapcsolat az Iranyitoszam entitáshoz"
        int Telepules_ID FK "Kapcsolat a Telepules entitáshoz"
    }

    Szavazokor {
        int ID PK "Egyedi azonosító"
        string SzavazokorCim "A szavazókör címe"
        int TelepulesiEgyeniValasztokerulet_ID FK "Kapcsolat a TEVK entitáshoz"
        int Varmegye_ID FK "Kapcsolat a Varmegye entitáshoz"
        int Telepules_ID FK "Kapcsolat a Telepules entitáshoz"
        int OrszagosEgyeniValasztokerulet_ID FK "Kapcsolat az OEVK entitáshoz"
    }

    Cim {
        int ID PK "Egyedi azonosító"
        string TeljesCim "A teljes cím, több mezőből összefűzve"
        string KozteruletNev "A közterület neve"
        string KozteruletJelleg "A közterület jellege"
        string Hazszam "A házszám"
        string Epulet "Az épület jele"
        string Lepcsohaz "A lépcsőház jele"
        int Sorrend "A betöltési sorrendet jelző sorszám"
        int Iranyitoszam_ID FK "Kapcsolat az Iranyitoszam entitáshoz (PIR)"
        int Szavazokor_ID FK "Kapcsolat a Szavazokor entitáshoz"
        int TelepulesiEgyeniValasztokerulet_ID FK "Kapcsolat a TEVK entitáshoz"
        int Varmegye_ID FK "Kapcsolat a Varmegye entitáshoz"
        int Telepules_ID FK "Kapcsolat a Telepules entitáshoz"
        int OrszagosEgyeniValasztokerulet_ID FK "Kapcsolat az OEVK entitáshoz"
    }

    Varmegye ||--o{ Telepules : "tartalmaz"
    Varmegye ||--o{ OrszagosEgyeniValasztokerulet : "tartalmaz"
    Telepules ||--o{ TelepulesiEgyeniValasztokerulet : "tartalmaz"
    Telepules }o--o{ Iranyitoszam_Telepules : "n-m kapcsolat"
    Iranyitoszam }o--o{ Iranyitoszam_Telepules : "n-m kapcsolat"
    OrszagosEgyeniValasztokerulet ||--o{ TelepulesiEgyeniValasztokerulet : "tartalmaz"
    TelepulesiEgyeniValasztokerulet ||--o{ Szavazokor : "tartalmaz"
    Szavazokor ||--o{ Cim : "tartalmaz"

    %% Redundáns, de a specifikációban jelölt kapcsolatok a jobb átláthatóságért

    Varmegye ||..o{ Cim : "hivatkozik"
    Telepules ||..o{ Cim : "hivatkozik"
    OrszagosEgyeniValasztokerulet ||..o{ Cim : "hivatkozik"
    TelepulesiEgyeniValasztokerulet ||..o{ Cim : "hivatkozik"
    Iranyitoszam ||..o{ Cim : "hivatkozik"
    Varmegye ||..o{ Szavazokor : "hivatkozik"
    Telepules ||..o{ Szavazokor : "hivatkozik"
    OrszagosEgyeniValasztokerulet ||..o{ Szavazokor : "hivatkozik"
```

##### Mintaadat: oevk.sample.json:

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

##### Mintaadat: Korzet_levalogatas20250702__ORSZAGOS.sample.csv:

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
