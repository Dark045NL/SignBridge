# Gebarentaal naar Tekst Demonstrator

## Projectoverzicht

Dit project betreft de ontwikkeling van een demonstrator die gebarentaal
omzet naar geschreven tekst met behulp van computer vision en machine
learning.

Het doel is niet om een volledig foutloos vertaalsysteem te bouwen, maar
om de technische haalbaarheid van gesture recognition aan te tonen en
het onderliggende AI-proces inzichtelijk te maken. De focus ligt op
inclusieve technologie en toegankelijkheid.

------------------------------------------------------------------------

## Doelstellingen

-   Laten zien hoe gebarenherkenning werkt met computer vision\
-   Het AI-proces visualiseren van camera-input tot tekstoutput\
-   De technische haalbaarheid van gebarentaalherkenning onderzoeken\
-   Beperkingen en toepassingsmogelijkheden bespreken\
-   Een interactieve demonstrator ontwikkelen voor presentaties en open
    dagen

------------------------------------------------------------------------

## Werking van het Systeem

1.  Het systeem registreert live videobeelden via een camera.\
2.  Hand-landmarks worden gedetecteerd met behulp van computer vision.\
3.  Relevante kenmerken van het gebaar worden geëxtraheerd.\
4.  Een getraind machine learning-model voorspelt het uitgevoerde
    gebaar.\
5.  Het voorspelde gebaar wordt omgezet naar leesbare tekst op het
    scherm.

------------------------------------------------------------------------

## Technologieën

-   Python\
-   OpenCV\
-   MediaPipe\
-   Machine learning framework\
-   Real-time videoprocessing

------------------------------------------------------------------------

## Installatie

``` bash
git clone https://github.com/gebruikersnaam/repository-naam.git
cd repository-naam
pip install -r requirements.txt
python main.py
```

------------------------------------------------------------------------

## Doelgroep

Deze demonstrator is ontwikkeld voor:

-   Bezoekers van open dagen\
-   Studenten\
-   Docenten\
-   Onderzoekers\
-   Beleidsmakers

Het doel is om AI-technologie begrijpelijk en toegankelijk te maken voor
een breed publiek.

------------------------------------------------------------------------

## Beperkingen

-   Beperkte woordenschat aan gebaren\
-   Gevoelig voor lichtomstandigheden en achtergrond\
-   Nauwkeurigheid afhankelijk van trainingsdata\
-   Geen vervanging voor professionele gebarentolken

------------------------------------------------------------------------

## Team

-   Michael Cuevas Fragoso\
-   Stephan Bisschop\
-   Wadie Boudaoud\
-   Jibbe Engelen
