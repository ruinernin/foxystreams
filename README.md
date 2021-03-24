FoxyStreams
===========
This plugin is an attempt to fill the gap of being [fast, light and easily
forkable][Reasoning]. It is not particularly useful on it's own and is intended
to be invoked by an external caller, such as [FoxyMeta][] or [OpenMeta][]. What
follows is general documentation. A [Quickstart][] bootstrap guide is available.

[Reasoning]: https://github.com/ruinernin/foxystreams/wiki/Reasoning

Installation
============
Repo
----
Add the repo below in the usual way via the _File Manager_ and install
`repository.nemoandcrush-X.X.X.zip`. Do not use the `-dev` repo as it is almost
guaranteed to contain broken code.



Config
======
General
-------
### Debrid Provider
After install choose Debrid providers to enable from settings. Lower values for
priority setting means a higher priority. Uncached items are added to the
highest (lowest numerical setting) priority debrid provider.

#### RealDebrid
Enable RealDebrid and the OAuth device code to enter on
https://real-debrid.com/device will appear on the launch.

#### Premiumize
Select Premiumize as the provider and enter a valid API Key.

### Scraper
It is recommended to leave this as 'TorrentApi' by default and use 'BitLord' as
a backup via an external player.

### Show cached only
Set this to only show cached items, removing the ability to add magnets to the
Debrid provider.

Search categories
-----------------
Choose categories to search within on TorrentApi. In general switches here
should be set based on the desired quality.

Definition of ranked switch from [API](https://torrentapi.org/apidocs_v2.txt):

> By default the api will return only ranked torrents ( internal ) , scene
> releases + -rarbg releases + -rartv releases.
>
> If you want other groups included in the results use the ranked parameter with
> a value of 0 to get them included.


Usage
=====
Throughout green color text indicates a cached item and red indicates a
non-cached item. Selecting a non-cached item adds it to the Debrid provider.

OpenMeta
--------
Supports usage via OpenMeta. Player JSON is in the default repo.

Downloads
---------
Lists downloads from Debrid provider.

List
----
Lists latest 100 items for selected category switches.

Search
------
Lists search results for user inputted string in selected category switches.
