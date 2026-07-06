# gui4gmns / qgis-plugin — network editing with GMNS write-back
Stack: PyQGIS. Unique: the classic NEXTA edit menu (move/create node & link, subarea cut, attribute
editing) on GMNS layers, plus projections/basemaps/printing from QGIS. Round-trip: load GMNS ->
edit -> validated GMNS save (schema check = encoding spec). Viewer conformance: contract §2 via a
"gui4gmns styles" layer-style pack; animation optional (QGIS temporal controller on 15-min bins).
