******************************************************************
*************************  ECON 644  *****************************
********************  Replication Project  ***********************
************************  Alan Lamb  *****************************
******************************************************************
          
capture log close
log using "LOG.smcl", replace
version 19.0
clear all
set more off

cd "`c(pwd)'"
capture mkdir "Graphs"
capture mkdir "Tables"



//////////               Question #1                    //////////  

use "Data/TrafficCitations2001.dta", clear

reg amount mphover if mphover >=10


* This data set and command produces the results discussed in the article
* The stastical significance can be observed with the overall models F-score
* of 0.00 or either the intercept or slope p-score, also both 0.00.



//////////               Question #2                    ////////// 

use "Data/TrafficCitations2001.dta", clear

keep if mphover >= 10 & !missing(amount)
gen expected = 50 + 10*(mphover - 10)
label variable expected "Expected Fine"

*create a table of fine types

gen fine_type = .
replace fine_type = 1 if amount == expected
replace fine_type = 2 if amount < expected
replace fine_type = 3 if amount > expected
label define fine_lbl 1 "congruent" 2 "below" 3 "above"
label values fine_type fine_lbl
tab fine_type

* Based on this table only 10.97% of all fines issued to motorists travelling
* 10 or more MPH over the speed limit were congruent with the legal formula.
* That means that the remaining 89.03% were based on officer discretion. 



//////////               Question #3                    //////////

clear all

* 1. Import and prepare population data
import delimited "Data/sub-est00int.csv", clear

keep if state == 25
keep if sumlev == 061
keep name popestimate2005

rename name municipality
rename popestimate2005 pop2005

replace municipality = subinstr(municipality, " city", "", .)
replace municipality = subinstr(municipality, " town", "", .)
replace municipality = subinstr(municipality, " Town", "", .)
replace municipality = strtrim(municipality)
replace municipality = stritrim(municipality)

collapse (mean) pop2005, by(municipality)
save popdata, replace

* 2. Import and prepare expenditures data
import excel "Data/GenFundExpenditures2005.xlsx", firstrow clear
rename Municipality municipality
save expenditures, replace

* 3. Import and prepare revenues data
import excel "Data/GenFundRevenues2005.xlsx", firstrow clear
rename Municipality municipality
save revenues, replace

* 4. Merge expenditures with population
use expenditures, clear
merge 1:1 municipality using popdata
keep if _merge == 3
drop _merge
save exp_pop, replace

* 5. Merge in revenues
use exp_pop, clear
merge 1:1 municipality using revenues
keep if _merge == 3
drop _merge

* 6. Generate variables
gen police_pc = Police / pop2005

* 7. Run correlation and regression
corr police_pc FinesandForfeitures
reg police_pc FinesandForfeitures

*After merging the Massachusetts expenditure, revenue, and population datasets,
*I examined the relationship between per capita police spending and fines and
*forfeitures revenue. The simple correlation between the two variables is
*positive but small (r ≈ 0.10), and the regression produces a similarly small
*positive coefficient (0.0000197) that is marginally statistically significant
*(p ≈ 0.06). This indicates that municipalities collecting more fines tend to
*spend slightly more on police per resident, although the relationship is weak.
*These results are consistent with the descriptive patterns reported by
*Makowsky and Stratmann, who emphasize that even small associations can reflect
*meaningful revenue-driven incentives in policing.



//////////               Question #4                    //////////

clear all

use "Data/Municipalities2001.dta", clear

* Create property value per capita
gen propval_pc = pvalue / pop2001

* Compute median
summ propval_pc, detail
scalar med = r(p50)

gen high_income = propval_pc > med
label define inc 0 "Low income" 1 "High income"
label values high_income inc

save muni_income, replace

* Merge into citation data using dor_code
use "Data/TrafficCitations2001.dta", clear

merge m:1 dor_code using muni_income

* Keep only matched observations
keep if _merge == 3
drop _merge

* Plot distributions
twoway (kdensity mphover if high_income==1, lcolor(blue)) ///
       (kdensity mphover if high_income==0, lcolor(red)), ///
       legend(order(1 "High income" 2 "Low income")) ///
       title("Recorded Speeds by Income Group") ///
       xtitle("MPH over limit") ytitle("Density")

graph export "Graphs/Q4_speeds_income.pdf", replace

twoway (kdensity amount if high_income==1, lcolor(blue)) ///
       (kdensity amount if high_income==0, lcolor(red)), ///
       legend(order(1 "High income" 2 "Low income")) ///
       title("Fine Amounts by Income Group") ///
       xtitle("Fine amount (USD)") ytitle("Density")

graph export "Graphs/Q4_fines_income.pdf", replace

*I classified municipalities as high  or low income based on whether their 2001 property value per capita was above or below the median, then merged this classification into the citation level dataset. Kernel density plots of recorded speeds and fine amounts for each income group each displayed a single clear peak, confirming that the distributions are unimodal as reported in the paper.



//////////               Question #5                    //////////

* Solution for percentage of drivers who were cited in their hometown

use "Data/Makowsky-Stratmann---Pol-Econ-at-Any-Speed.dta", clear

summ intown

*The variable intown indicates whether the driver received the citation in their home municipality. Summarizing this variable shows that 22.6% of drivers were cited in their home town, while 77.4% were cited outside their home town. Under this interpretation, the majority of citations involve drivers who are out of town at the time of the stop.

* Solution for officers administering fines outside of their home jurisdiction
* based on officers issuing citations in multiple jurisdictions.

use "Data/TrafficCitations2001.dta", clear

* Keep only local officers
keep if statepol == 0

* Tag one observation per officer–municipality pair
egen muni_tag = tag(officercode locate2)

* Count number of distinct municipalities per officer
bysort officercode: egen num_muni = total(muni_tag)

* Flag officers who worked in 2+ municipalities
gen multi_muni = (num_muni >= 2)

* Reduce to one row per officer
bysort officercode: keep if _n == 1

* Summarize
summ multi_muni
display r(mean)*100

* Officers who issue citations in two or more municipalities must have worked
* outside their home town at least once. I flag these officers and compute the
* share among all local officers, which gives a lower-bound estimate of
* 19.07%.



//////////               Question #6                    //////////

use "Data/Makowsky-Stratmann---Pol-Econ-at-Any-Speed.dta", clear

* 1. Ticket rate for local (in-town) drivers
summarize nowarn if intown == 1
display "Local ticket rate = " r(mean)*100

* 2. Ticket rate for out-of-state drivers
summarize nowarn if outstate == 1
display "Out-of-state ticket rate = " r(mean)*100

* 3. Average fine for local drivers (only those who got a ticket)
summarize amount if intown == 1 & nowarn == 1
display "Local average fine = " r(mean)

* 4. Average fine for out-of-state drivers (only those who got a ticket)
summarize amount if outstate == 1 & nowarn == 1
display "Out-of-state average fine = " r(mean)

*Using intown to identify local drivers (those stopped in their home municipality),
*local drivers received tickets in about 31% of stops compared to 66% for
*out-of-state drivers. Among those ticketed, local drivers paid an average fine
*of approximately $117 versus $127 for out-of-state drivers. These results
*closely match the figures reported by Makowsky and Stratmann (30%, 66%, $118,
*and $126 respectively), confirming that out-of-state drivers face both a higher
*probability of citation and higher fines.



//////////               Question #7 — Table 1                    //////////

use "Data/TrafficCitations2001.dta", clear

* Merge municipality data
merge m:1 locate2 using "Data/Municipalities2001.dta"
keep if _merge == 3
drop _merge

* Generate variables
gen female = (sex == "F")
gen propval_pc = pvalue / pop2001
gen hosp_pct = accemplp * 100
gen citation = nowarn

* Label all variables
label variable citation "Citation issued = 1, 0 otherwise"
label variable outstate "Out of state driver = 1, 0 otherwise"
label variable outtown "Out of town driver = 1, 0 otherwise"
label variable orloss01 "Override loss = 1, 0 otherwise"
label variable courtdistance "Distance to court (miles)"
label variable hosp_pct "Hospitality employment (%)"
label variable mphover "MPH over speed limit"
label variable propval_pc "Property value (per capita)"
label variable black "Black = 1, 0 otherwise"
label variable hispanic "Hispanic = 1, 0 otherwise"
label variable female "Female = 1, 0 otherwise"
label variable age "Age"
label variable statepol "State police = 1, 0 otherwise"
label variable cdl2 "Commercial driver's license = 1, 0 otherwise"
label variable amount "Fine amount / $"

* Column 1: Citation sample (all observations)
estpost summarize citation outstate outtown orloss01 courtdistance hosp_pct mphover ///
    propval_pc black hispanic female age statepol cdl2
est store col1

* Column 2: Fine sample (only tickets issued)
estpost summarize amount outstate outtown orloss01 courtdistance hosp_pct mphover ///
    propval_pc black hispanic female age statepol cdl2 if citation==1
est store col2

* Export table
esttab col1 col2 using "Tables/table1.rtf", ///
    cells("mean(fmt(3)) sd(fmt(3))") ///
    collabels("Mean" "Std. dev.") ///
    mtitles("Analysis of citations (N = 68,357)" "Analysis of fine $ amount (N = 31,674)") ///
    label nonumber noobs ///
    title("Table 1 — Variable Summary Statistics") ///
    replace


********************************************************************************
* MASSACHUSETTS COUNTY MAP WITH CITATION SHADING 
********************************************************************************

cd "`c(pwd)'"

*------------------------------------------------------------
* 1. Unzip and import shapefile 
*------------------------------------------------------------
unzipfile "cb_2024_us_county_500k.zip", replace

spshape2dta "cb_2024_us_county_500k", replace

*------------------------------------------------------------
* 2. Keep only Massachusetts
*------------------------------------------------------------
use "cb_2024_us_county_500k.dta", clear
keep if STATEFP == "25"
sort _ID
save "ma_counties_attr.dta", replace

use "cb_2024_us_county_500k_shp.dta", clear
sort _ID
save "ma_counties_shp.dta", replace

*------------------------------------------------------------
* 3. Merge citations
*------------------------------------------------------------
use "ma_counties_attr.dta", clear
merge 1:1 GEOID using "ma_counties_with_citations.dta"
keep if _merge == 3
drop _merge
sort _ID
save "ma_counties_merged.dta", replace

*------------------------------------------------------------
* 4. Draw the choropleth map
*------------------------------------------------------------
use "ma_counties_merged.dta", clear

grmap citations using "ma_counties_shp.dta", ///
    id(_ID) ///
    fcolor(Blues) ///
    ocolor(black ..) ///
    osize(vthin ..) ///
    legend(position(11) title("Citations Issued")) ///
    clmethod(custom) ///
	clbreaks(0 500 2000 5000 10000 15000) ///
	label(data("ma_counties_merged.dta") xcoord(_CX) ycoord(_CY) ///
          label(NAME) size(*0.7) color(black)) ///
    title("Massachusetts Traffic Citations by County", size(*1.2))
	
graph export "Graphs/MA_citations_map.pdf", replace



//////////          Question #8 — Municipality-Level Table          //////////

use "Data/Makowsky-Stratmann---Pol-Econ-at-Any-Speed.dta", clear

gen citation = nowarn
gen accemplp_pct = accemplp * 100

collapse (count) num_stops    = citation ///
         (sum)   num_citations = citation ///
         (mean)  pop2001 ///
         (mean)  pvaluepc ///
         (mean)  orloss01 ///
         (mean)  accemplp_pct ///
         (mean)  courtdistance ///
         (mean)  statepol, ///
         by(locate2)

label variable num_stops      "Total traffic stops"
label variable num_citations  "Citations issued"
label variable pop2001        "Population (2001)"
label variable pvaluepc       "Property value (per capita)"
label variable orloss01       "Override loss = 1, 0 otherwise"
label variable accemplp_pct   "Hospitality employment (% of total employment)"
label variable courtdistance  "Distance to court (miles)"
label variable statepol       "Share of stops by state police"

estpost summarize num_stops num_citations pop2001 pvaluepc ///
                  orloss01 accemplp_pct courtdistance statepol

esttab using "Tables/table_q8.rtf", ///
    cells("mean(fmt(3)) sd(fmt(3)) count(fmt(0))") ///
    collabels("Mean" "Std. dev." "N") ///
    label nonumber noobs ///
    title("Table — Municipality-Level Summary Statistics") ///
    replace


	
//////////     Question #9 — Table 2A Columns (1)-(4)    //////////

clear all
use "Data/Makowsky-Stratmann---Pol-Econ-at-Any-Speed.dta", clear

*------------------------------------------------------------
// Column (1)
*------------------------------------------------------------
dprobit nowarn outtown outstate orloss01 ///
    lnmphover lnpvaluepc black hispanic female lnage femalelnage cdl2 ///
    statepol otstatepol osstatepol splnpvaluepc sporloss01, ///
    cluster(dor_code)

outreg2 using "Tables/table2a.doc", ///
    replace word bdec(3) alpha(0.01, 0.05, 0.10) ctitle("Column 1")

*------------------------------------------------------------
// Column (2)
*------------------------------------------------------------
dprobit nowarn outtown outstate orloss01 otorloss01 osorloss01 ///
    lnmphover lnpvaluepc black hispanic female lnage femalelnage cdl2 ///
    statepol otstatepol osstatepol splnpvaluepc sporloss01, ///
    cluster(dor_code)

outreg2 using "Tables/table2a.doc", ///
    append word bdec(3) alpha(0.01, 0.05, 0.10) ctitle("Column 2")

*------------------------------------------------------------
// Column (3) - ADD otorloss01!
*------------------------------------------------------------
dprobit nowarn outtown lncourtdist orloss01 otorloss01 ldorloss01 ///
    lnmphover lnpvaluepc black hispanic female lnage femalelnage cdl2 ///
    statepol otstatepol splncourtdist splnpvaluepc sporloss01, ///
    cluster(dor_code)

outreg2 using "Tables/table2a.doc", ///
    append word bdec(3) alpha(0.01, 0.05, 0.10) ctitle("Column 3")

*------------------------------------------------------------
// Column (4) - NO orloss01!
*------------------------------------------------------------
dprobit nowarn outtown outstate ///
    lnkaccemplp otlnkaccemplp oslnkaccemplp ///
    lnmphover lnpvaluepc black hispanic female lnage femalelnage cdl2 ///
    statepol otstatepol osstatepol splnkaccemplp splnpvaluepc, ///
    cluster(dor_code)

outreg2 using "Tables/table2a.doc", ///
    append word bdec(3) alpha(0.01, 0.05, 0.10) ctitle("Column 4")
	

	
//////////     Question #10 — Table 4 Column (1)    //////////

clear all
use "Data/Makowsky-Stratmann---Pol-Econ-at-Any-Speed.dta", clear

dprobit nowarn outtown lncourtdist ///
    orloss01 otorloss01 ldorloss01 ///
    lnmphover lnpvaluepc black hispanic female lnage femalelnage cdl2 ///
    statepol otstatepol splncourtdist splnpvaluepc sporloss01 ///
    if outstate == 0
	
* Export with outreg2
outreg2 using "Tables/table4_col1.doc", ///
    replace ///
    word ///
    keep(outtown lncourtdist statepol otstatepol splncourtdist) ///
    title("Table 4 Column 1") ///
    bdec(3) ///
    alpha(0.01, 0.05, 0.10)



//////////     Question #11 — Table 5     //////////

clear all
use "Data/Makowsky-Stratmann---Pol-Econ-at-Any-Speed.dta", clear

* Encode stop location for municipality fixed effects
encode locate2, gen(stop_muni)

* Create town size × intown interactions manually
gen town1_x_in = pq1 * intown
gen town2_x_in = pq2 * intown
gen town3_x_in = pq3 * intown
gen town4_x_in = pq4 * intown

* Label variables for table output
label variable intown "In town"
label variable town1_x_in "Town size 1 × in town"
label variable town2_x_in "Town size 2 × in town"
label variable town3_x_in "Town size 3 × in town"
label variable town4_x_in "Town size 4 × in town"
label variable outstate "Out of state"
label variable lncourtdist "Log distance to court"

* Run regressions
eststo clear

eststo col1: areg nowarn intown lncourtdist ///
    lnmphover black hispanic female lnage femalelnage cdl2 ///
    if statepol==0, absorb(stop_muni) cluster(stop_muni)

eststo col2: areg nowarn town1_x_in town2_x_in town3_x_in town4_x_in lncourtdist ///
    lnmphover black hispanic female lnage femalelnage cdl2 ///
    if statepol==0, absorb(stop_muni) cluster(stop_muni)

eststo col3: areg nowarn intown outstate lncourtdist ///
    lnmphover black hispanic female lnage femalelnage cdl2 ///
    if statepol==1, absorb(stop_muni) cluster(stop_muni)

eststo col4: areg nowarn town1_x_in town2_x_in town3_x_in town4_x_in outstate lncourtdist ///
    lnmphover black hispanic female lnage femalelnage cdl2 ///
    if statepol==1, absorb(stop_muni) cluster(stop_muni)

* Export table
esttab col1 col2 col3 col4 using "Tables/table5.rtf", replace ///
    b(3) se(3) ///
    star(* 0.10 ** 0.05 *** 0.01) ///
    label ///
    title("Table 5 — OLS: Probability of Fines for Local Drivers and Town Size") ///
    mtitles("(1)" "(2)" "(3)" "(4)") ///
    keep(intown town1_x_in town2_x_in town3_x_in town4_x_in outstate lncourtdist _cons) ///
    order(intown town1_x_in town2_x_in town3_x_in town4_x_in outstate lncourtdist _cons) ///
    stats(N r2, fmt(0 3) labels("Observations" "R-squared"))


	
log close
