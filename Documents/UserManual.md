Instruction manual for AutomatingCBC

Preparing a new count circle

- From 121st Christmas Bird Count: Map of Active Circles
https://www.arcgis.com/apps/View/index.html?appid=ac275eeb01434cedb1c5dcd0fd3fc7b4
get the circle parameters. Copy an existing parameters file in 
parameters/Local and name with the 4 character abbreviation, e.g. CASJ-2020-parameters.xlsx

Creating a Parameters file
- copy the sample Parameters file
- rename e.g. CASJ-2020-parameters.xlsx
- use data from xxx to fill in circle information

121st Christmas Bird Count: Map of Active Circles  
https://www.arcgis.com/apps/View/index.html?appid=ac275eeb01434cedb1c5dcd0fd3fc7b4


Copy the checklist for the count to Inputs/Parse
- It should be named CASJ-2020-checklist.pdf (or .xlsx etc)

Creating an initial Annotations file
- Run parse to create a checklist
- Copy e.g. Outputs/CASJ-2020-Single.xlsx to Inputs/Parse and rename CAMP-2020-Annotations.xlsx
- Add the extra columns from a sample Annotations file

Subsequent Annotations files
- Copy the previous one and rename with current year
- Update any entries
- New entries can be added at the bottom

Creating a checklist
- put copy of pdf in Inputs/Parse
- Run Service-Parse
- make Annotations file and mark as desired
- add a column to ground-truths.xlsx, e.g. CAMP-2020
- Sort the -Single file by Common Name, and mark up ground_truths
- Run Service-Parse again


This tool uses a data-driven approach. Although initial setup takes some time, subsequent
years will be much easier.

# Using the Summary Report

The summary report has several sheets, each with varying levels of information and detail 
about the count data.

## Final Checklist Sheet
The main sheet that will be used as a reference when entering data into the official Audubon site is
the "Final Checklist" sheet. It shows grand totals for all species seen, collated from
the individual sector reports. 
To minimize the effort when entering this data, you will apply some filters
and sort by the NACC sort order, which is what Audubon uses.

- Click on the "Total" column, and uncheck "0". Now only species that were seen on count day are shown
- Click on the filter button for the "NACC_SORT_ORDER" column, and click "Sort Ascending"
- Click on the filter button for the "Category" column, and uncheck everything but "species". This will drop
all of the uncountable entries such as SPUH (e.g. accipiter sp.) and SLASH (e.g. Greater/Lesser Scaup)

## Rarities sheet
The “Rarities” sheet shows all sightings that require a Rare Bird Form, either because 
it was explicitly marked in the Annotations file, or because the species was not on the 
master checklist. The "Reason" field will indicate this with "explicit" (marked rare
in the Annotations file) or "missing" (not on the master checklist). All of the other
data on the sheet is pulled directly from eBird, and may help when filling out the Rare Bird 
Form.

## AutoParty sheet

The “AutoParty” sheet automatically creates parties based on locations and sets of people.

# Using the Sector Reports

Many counts are broken up into sectors to make management of the count easier. For three 
Bay Area counts (CASJ, CACR and CAPA), KML files with sector information are available.

The sector reports have a couple of hidden features to ensure an accurate count. Each column
is an individual checklist. The column is named with several pieces of information about
the checklist. For example,  ```L370800-S77755885-08:57-John Hurley``` has a location ID of
L370800 ("Alum Rock Park"), a checklist ID of S77755885 (https://ebird.org/checklist/S77755885),
the time for the checklist, and the observer name.


Refer to the "Individual Details" sheet of the count summary for complete details of
each checklist, including location name and the checklist URL.

If one person at a location filed a checklist, or if that checklist was shared and no
further modifications were done (i.e. species seen only by one person), the results
can be added into the count directly.

# E Bird Tips
- Don't use an X for a total; estimate to nearest 10, 100, 1000 etc
- Compilers/Sector Leaders: specify a list of hotspots to use in advance
- [see eBird article on this]

From Azevedo email 01-13-21
I don’t know if this will be helpful to you, but I have enclosed spreadsheets that detail and summarize all of the eBird activity on count day for CASJ, 2020-12-20.

Each sector report has individual columns for each party. If multiple people birded the same spot, the columns are highlighted to group them.

The summary report has various sheets. The “Final Checklist” sheet shows grand totals for all species seen. The “Rarities” sheet shows all sightings that require a Rare Bird Form, either because you explicitly marked it, or because the species was not on the list. The “AutoParty” sheet automatically creates parties based on locations and sets of people.

Finally, CASJ-CountCircleMap.html shows the location of each observation. Clicking on an observation shows info about the observation and has a link to the eBird checklist.
