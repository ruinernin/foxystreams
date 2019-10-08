Installation
============
Either add the repo via the File manager or install the latest zip.
Instructions for how to do so is outside of the scope of this document.

Repo
----
`https://ruinernin.github.io`


Config
======

Debrid
------
After install choose a Debrid provider from settings.

### RealDebrid

Simply choose RealDebrid and the OAuth device code to enter on
https://real-debrid.com/device will appear on the launch.

### Premiumize

Select Premiumize as the provider and enter a valid API Key.

Search
------
Choose categories to search within on rarbg.

Definition of ranked switch from [api](https://torrentapi.org/apidocs_v2.txt)

    By default the api will return only ranked torrents ( internal ) , scene releases + -rarbg releases + -rartv releases.
    If you want other groups included in the results use the ranked parameter with a value of 0 to get them included.


Usage
=====
Throughout green color text indicates a cached item and red indicates a
non-cached item. Selecting a non-cached item adds it to the Debrid provider.

Downloads
---------
Lists downloads from Debrid provider.

List
----
Lists latest 100 items for selected category switches.

Search
------
Lists search results for user inputted string in selected category switches.


OpenMeta
========
Supports usage via OpenMeta. Player json currently available at
https://github.com/ruinernin/foxystreams-omp
