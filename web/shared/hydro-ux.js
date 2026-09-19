/* ==========================================================================
   Hydro-Art shared UX engine (classic script — exposes window.HydroUX)
   --------------------------------------------------------------------------
   Common client-side model shared by every web/ prototype so the mockups stay
   consistent and DRY. Loaded with a plain <script src> (not an ES module) so
   the prototypes keep working over file:// without a build or dev server.

   What lives here (the parts every prototype needs):
     - Ground-truth option data (states, counties, palettes, months) mirrored
       from the Python pipeline (src/config.py, src/coloring.py, render_common).
     - A deterministic procedural river-network generator + SVG builder, so a
       preview is available with no datasets (same trick as web/index.html).
     - A seasonal monthly-flow *simulation* mirroring tools/monthly_flow.py:
       widths are scaled on a fixed year-max so seasonal swell/retreat shows.
     - applyStyles(): maps a UX `state` object onto the live SVG.
     - mapping helpers: translate UX selections back into build.py CLI + YAML.
   None of this touches the real pipeline; it is a faithful client-side stand-in.
   ========================================================================== */
"use strict";

(function (global) {

  // ---- Ground-truth option data (mirrors the Python side) -----------------

  // src/config.SUPPORTED_REGIONS + src/datasets.REGION_HUC4 — all 50 US states.
  const STATES = [
    { id: "Maine", label: "Maine", huc4: ["0101","0102","0103","0104","0105","0106"] },
    { id: "New Hampshire", label: "New Hampshire", huc4: ["0104","0106","0107","0108"] },
    { id: "Vermont", label: "Vermont", huc4: ["0108","0202","0430"] },
    { id: "Massachusetts", label: "Massachusetts", huc4: ["0107","0108","0109","0110","0202"] },
    { id: "Rhode Island", label: "Rhode Island", huc4: ["0109","0110"] },
    { id: "Connecticut", label: "Connecticut", huc4: ["0108","0110"] },
    { id: "New York", label: "New York", huc4: ["0110","0202","0203","0204","0205","0412","0413","0414","0427","0429","0430","0501"] },
    { id: "New Jersey", label: "New Jersey", huc4: ["0202","0203","0204"] },
    { id: "Pennsylvania", label: "Pennsylvania", huc4: ["0204","0205","0206","0207","0412","0413","0501","0502","0503"] },
    { id: "Delaware", label: "Delaware", huc4: ["0204","0206","0208"] },
    { id: "Maryland", label: "Maryland", huc4: ["0204","0205","0206","0207","0208","0502"] },
    { id: "Virginia", label: "Virginia", huc4: ["0204","0207","0208","0301","0505","0507","0601"] },
    { id: "West Virginia", label: "West Virginia", huc4: ["0207","0502","0503","0505","0507","0509"] },
    { id: "North Carolina", label: "North Carolina", huc4: ["0301","0302","0303","0304","0305","0306","0505","0601","0602"] },
    { id: "South Carolina", label: "South Carolina", huc4: ["0304","0305","0306"] },
    { id: "Georgia", label: "Georgia", huc4: ["0306","0307","0311","0312","0313","0315","0602"] },
    { id: "Florida", label: "Florida", huc4: ["0307","0308","0309","0310","0311","0312","0313","0314"] },
    { id: "Alabama", label: "Alabama", huc4: ["0313","0314","0315","0316","0317","0602","0603"] },
    { id: "Mississippi", label: "Mississippi", huc4: ["0316","0317","0318","0603","0801","0802","0803","0806","0807"] },
    { id: "Tennessee", label: "Tennessee", huc4: ["0511","0513","0601","0602","0603","0604","0801"] },
    { id: "Kentucky", label: "Kentucky", huc4: ["0507","0509","0510","0511","0513","0514","0604","0801"] },
    { id: "Ohio", label: "Ohio", huc4: ["0410","0411","0412","0503","0504","0506","0508","0509","0512"] },
    { id: "Indiana", label: "Indiana", huc4: ["0404","0405","0410","0508","0509","0512","0514","0712"] },
    { id: "Illinois", label: "Illinois", huc4: ["0404","0512","0514","0706","0708","0709","0711","0712","0713","0714"] },
    { id: "Michigan", label: "Michigan", huc4: ["0401","0402","0403","0404","0405","0406","0407","0408","0409","0410","0418","0420","0424"] },
    { id: "Wisconsin", label: "Wisconsin", huc4: ["0401","0402","0403","0404","0703","0704","0705","0706","0707","0709","0712"] },
    { id: "Minnesota", label: "Minnesota", huc4: ["0401","0701","0702","0703","0704","0706","0708","0710","0902","0903","1017","1023"] },
    { id: "Iowa", label: "Iowa", huc4: ["0702","0706","0708","0710","0711","1017","1023","1024","1028"] },
    { id: "Missouri", label: "Missouri", huc4: ["0711","0714","0801","0802","1024","1028","1029","1030","1101","1107"] },
    { id: "Arkansas", label: "Arkansas", huc4: ["0801","0802","0803","0804","0805","1101","1107","1111","1114"] },
    { id: "Louisiana", label: "Louisiana", huc4: ["0318","0803","0804","0805","0806","0807","0808","0809","1114","1201","1204"] },
    { id: "North Dakota", label: "North Dakota", huc4: ["0901","0902","1006","1010","1011","1013","1016"] },
    { id: "South Dakota", label: "South Dakota", huc4: ["0702","0902","1011","1012","1013","1014","1015","1016","1017"] },
    { id: "Nebraska", label: "Nebraska", huc4: ["1012","1014","1015","1017","1018","1019","1020","1021","1022","1023","1024","1025","1027"] },
    { id: "Kansas", label: "Kansas", huc4: ["1024","1025","1026","1027","1029","1030","1103","1104","1106","1107"] },
    { id: "Oklahoma", label: "Oklahoma", huc4: ["1104","1105","1106","1107","1109","1110","1111","1112","1113","1114"] },
    { id: "Texas", label: "Texas", huc4: ["1109","1110","1112","1113","1114","1201","1202","1203","1204","1205","1206","1207","1208","1209","1210","1211","1304","1305","1307","1308","1309"] },
    { id: "Montana", label: "Montana", huc4: ["0904","1002","1003","1004","1005","1006","1007","1008","1009","1010","1011","1701"] },
    { id: "Idaho", label: "Idaho", huc4: ["1601","1602","1701","1704","1705","1706"] },
    { id: "Wyoming", label: "Wyoming", huc4: ["1002","1007","1008","1009","1011","1012","1015","1018","1019","1404","1405","1601","1704"] },
    { id: "Nevada", label: "Nevada", huc4: ["1501","1503","1602","1604","1605","1606","1704","1705","1712","1808","1809"] },
    { id: "Utah", label: "Utah", huc4: ["1403","1404","1405","1406","1407","1408","1501","1601","1602","1603","1704"] },
    { id: "Colorado", label: "Colorado", huc4: ["1018","1019","1025","1026","1102","1103","1104","1301","1401","1402","1403","1404","1405","1408"] },
    { id: "Arizona", label: "Arizona", huc4: ["1407","1408","1501","1502","1503","1504","1505","1506","1507","1508"] },
    { id: "New Mexico", label: "New Mexico", huc4: ["1104","1108","1109","1110","1112","1205","1208","1301","1302","1303","1305","1306","1307","1408","1502","1504"] },
    { id: "Oregon", label: "Oregon", huc4: ["1604","1705","1706","1707","1708","1709","1710","1712","1801","1802"] },
    { id: "Washington", label: "Washington", huc4: ["1701","1702","1703","1706","1707","1708","1710","1711"] },
    { id: "California", label: "California", huc4: ["1503","1605","1606","1801","1802","1803","1804","1805","1806","1807","1808","1809","1810"] },
    { id: "Hawaii", label: "Hawaii", huc4: ["2001","2002","2003","2004","2005","2006","2007","2008"] },
    { id: "Alaska", label: "Alaska", huc4: ["1901","1902","1903","1905","1906","1907","1908","1909"] },
  ];

  // Real county rosters (Census cb_2023_us_county_500k) for all 50 states.
  // Pipeline matches on NAME (bare, no " County" suffix).
  const COUNTIES = {
    Maine: ["Androscoggin","Aroostook","Cumberland","Franklin","Hancock","Kennebec","Knox",
      "Lincoln","Oxford","Penobscot","Piscataquis","Sagadahoc","Somerset","Waldo",
      "Washington","York"],
    "New Hampshire": ["Belknap","Carroll","Cheshire","Coos","Grafton","Hillsborough","Merrimack",
      "Rockingham","Strafford","Sullivan"],
    Vermont: ["Addison","Bennington","Caledonia","Chittenden","Essex","Franklin","Grand Isle",
      "Lamoille","Orange","Orleans","Rutland","Washington","Windham","Windsor"],
    Massachusetts: ["Barnstable","Berkshire","Bristol","Dukes","Essex","Franklin","Hampden","Hampshire",
      "Middlesex","Nantucket","Norfolk","Plymouth","Suffolk","Worcester"],
    "Rhode Island": ["Bristol","Kent","Newport","Providence","Washington"],
    Connecticut: ["Capitol","Greater Bridgeport","Lower Connecticut River Valley","Naugatuck Valley",
      "Northeastern Connecticut","Northwest Hills","South Central Connecticut",
      "Southeastern Connecticut","Western Connecticut"],
    "New York": ["Albany","Allegany","Bronx","Broome","Cattaraugus","Cayuga","Chautauqua","Chemung",
      "Chenango","Clinton","Columbia","Cortland","Delaware","Dutchess","Erie","Essex",
      "Franklin","Fulton","Genesee","Greene","Hamilton","Herkimer","Jefferson","Kings",
      "Lewis","Livingston","Madison","Monroe","Montgomery","Nassau","New York","Niagara",
      "Oneida","Onondaga","Ontario","Orange","Orleans","Oswego","Otsego","Putnam","Queens",
      "Rensselaer","Richmond","Rockland","Saratoga","Schenectady","Schoharie","Schuyler",
      "Seneca","St. Lawrence","Steuben","Suffolk","Sullivan","Tioga","Tompkins","Ulster",
      "Warren","Washington","Wayne","Westchester","Wyoming","Yates"],
    "New Jersey": ["Atlantic","Bergen","Burlington","Camden","Cape May","Cumberland","Essex",
      "Gloucester","Hudson","Hunterdon","Mercer","Middlesex","Monmouth","Morris","Ocean",
      "Passaic","Salem","Somerset","Sussex","Union","Warren"],
    Pennsylvania: ["Adams","Allegheny","Armstrong","Beaver","Bedford","Berks","Blair","Bradford","Bucks",
      "Butler","Cambria","Cameron","Carbon","Centre","Chester","Clarion","Clearfield",
      "Clinton","Columbia","Crawford","Cumberland","Dauphin","Delaware","Elk","Erie",
      "Fayette","Forest","Franklin","Fulton","Greene","Huntingdon","Indiana","Jefferson",
      "Juniata","Lackawanna","Lancaster","Lawrence","Lebanon","Lehigh","Luzerne","Lycoming",
      "McKean","Mercer","Mifflin","Monroe","Montgomery","Montour","Northampton",
      "Northumberland","Perry","Philadelphia","Pike","Potter","Schuylkill","Snyder",
      "Somerset","Sullivan","Susquehanna","Tioga","Union","Venango","Warren","Washington",
      "Wayne","Westmoreland","Wyoming","York"],
    Delaware: ["Kent","New Castle","Sussex"],
    Maryland: ["Allegany","Anne Arundel","Baltimore","Baltimore","Calvert","Caroline","Carroll",
      "Cecil","Charles","Dorchester","Frederick","Garrett","Harford","Howard","Kent",
      "Montgomery","Prince George's","Queen Anne's","Somerset","St. Mary's","Talbot",
      "Washington","Wicomico","Worcester"],
    Virginia: ["Accomack","Albemarle","Alexandria","Alleghany","Amelia","Amherst","Appomattox",
      "Arlington","Augusta","Bath","Bedford","Bland","Botetourt","Bristol","Brunswick",
      "Buchanan","Buckingham","Buena Vista","Campbell","Caroline","Carroll","Charles City",
      "Charlotte","Charlottesville","Chesapeake","Chesterfield","Clarke","Colonial Heights",
      "Covington","Craig","Culpeper","Cumberland","Danville","Dickenson","Dinwiddie",
      "Emporia","Essex","Fairfax","Fairfax","Falls Church","Fauquier","Floyd","Fluvanna",
      "Franklin","Franklin","Frederick","Fredericksburg","Galax","Giles","Gloucester",
      "Goochland","Grayson","Greene","Greensville","Halifax","Hampton","Hanover",
      "Harrisonburg","Henrico","Henry","Highland","Hopewell","Isle of Wight","James City",
      "King George","King William","King and Queen","Lancaster","Lee","Lexington","Loudoun",
      "Louisa","Lunenburg","Lynchburg","Madison","Manassas","Manassas Park","Martinsville",
      "Mathews","Mecklenburg","Middlesex","Montgomery","Nelson","New Kent","Newport News",
      "Norfolk","Northampton","Northumberland","Norton","Nottoway","Orange","Page",
      "Patrick","Petersburg","Pittsylvania","Poquoson","Portsmouth","Powhatan",
      "Prince Edward","Prince George","Prince William","Pulaski","Radford","Rappahannock",
      "Richmond","Richmond","Roanoke","Roanoke","Rockbridge","Rockingham","Russell","Salem",
      "Scott","Shenandoah","Smyth","Southampton","Spotsylvania","Stafford","Staunton",
      "Suffolk","Surry","Sussex","Tazewell","Virginia Beach","Warren","Washington",
      "Waynesboro","Westmoreland","Williamsburg","Winchester","Wise","Wythe","York"],
    "West Virginia": ["Barbour","Berkeley","Boone","Braxton","Brooke","Cabell","Calhoun","Clay","Doddridge",
      "Fayette","Gilmer","Grant","Greenbrier","Hampshire","Hancock","Hardy","Harrison",
      "Jackson","Jefferson","Kanawha","Lewis","Lincoln","Logan","Marion","Marshall","Mason",
      "McDowell","Mercer","Mineral","Mingo","Monongalia","Monroe","Morgan","Nicholas",
      "Ohio","Pendleton","Pleasants","Pocahontas","Preston","Putnam","Raleigh","Randolph",
      "Ritchie","Roane","Summers","Taylor","Tucker","Tyler","Upshur","Wayne","Webster",
      "Wetzel","Wirt","Wood","Wyoming"],
    "North Carolina": ["Alamance","Alexander","Alleghany","Anson","Ashe","Avery","Beaufort","Bertie",
      "Bladen","Brunswick","Buncombe","Burke","Cabarrus","Caldwell","Camden","Carteret",
      "Caswell","Catawba","Chatham","Cherokee","Chowan","Clay","Cleveland","Columbus",
      "Craven","Cumberland","Currituck","Dare","Davidson","Davie","Duplin","Durham",
      "Edgecombe","Forsyth","Franklin","Gaston","Gates","Graham","Granville","Greene",
      "Guilford","Halifax","Harnett","Haywood","Henderson","Hertford","Hoke","Hyde",
      "Iredell","Jackson","Johnston","Jones","Lee","Lenoir","Lincoln","Macon","Madison",
      "Martin","McDowell","Mecklenburg","Mitchell","Montgomery","Moore","Nash",
      "New Hanover","Northampton","Onslow","Orange","Pamlico","Pasquotank","Pender",
      "Perquimans","Person","Pitt","Polk","Randolph","Richmond","Robeson","Rockingham",
      "Rowan","Rutherford","Sampson","Scotland","Stanly","Stokes","Surry","Swain",
      "Transylvania","Tyrrell","Union","Vance","Wake","Warren","Washington","Watauga",
      "Wayne","Wilkes","Wilson","Yadkin","Yancey"],
    "South Carolina": ["Abbeville","Aiken","Allendale","Anderson","Bamberg","Barnwell","Beaufort","Berkeley",
      "Calhoun","Charleston","Cherokee","Chester","Chesterfield","Clarendon","Colleton",
      "Darlington","Dillon","Dorchester","Edgefield","Fairfield","Florence","Georgetown",
      "Greenville","Greenwood","Hampton","Horry","Jasper","Kershaw","Lancaster","Laurens",
      "Lee","Lexington","Marion","Marlboro","McCormick","Newberry","Oconee","Orangeburg",
      "Pickens","Richland","Saluda","Spartanburg","Sumter","Union","Williamsburg","York"],
    Georgia: ["Appling","Atkinson","Bacon","Baker","Baldwin","Banks","Barrow","Bartow","Ben Hill",
      "Berrien","Bibb","Bleckley","Brantley","Brooks","Bryan","Bulloch","Burke","Butts",
      "Calhoun","Camden","Candler","Carroll","Catoosa","Charlton","Chatham","Chattahoochee",
      "Chattooga","Cherokee","Clarke","Clay","Clayton","Clinch","Cobb","Coffee","Colquitt",
      "Columbia","Cook","Coweta","Crawford","Crisp","Dade","Dawson","DeKalb","Decatur",
      "Dodge","Dooly","Dougherty","Douglas","Early","Echols","Effingham","Elbert","Emanuel",
      "Evans","Fannin","Fayette","Floyd","Forsyth","Franklin","Fulton","Gilmer","Glascock",
      "Glynn","Gordon","Grady","Greene","Gwinnett","Habersham","Hall","Hancock","Haralson",
      "Harris","Hart","Heard","Henry","Houston","Irwin","Jackson","Jasper","Jeff Davis",
      "Jefferson","Jenkins","Johnson","Jones","Lamar","Lanier","Laurens","Lee","Liberty",
      "Lincoln","Long","Lowndes","Lumpkin","Macon","Madison","Marion","McDuffie","McIntosh",
      "Meriwether","Miller","Mitchell","Monroe","Montgomery","Morgan","Murray","Muscogee",
      "Newton","Oconee","Oglethorpe","Paulding","Peach","Pickens","Pierce","Pike","Polk",
      "Pulaski","Putnam","Quitman","Rabun","Randolph","Richmond","Rockdale","Schley",
      "Screven","Seminole","Spalding","Stephens","Stewart","Sumter","Talbot","Taliaferro",
      "Tattnall","Taylor","Telfair","Terrell","Thomas","Tift","Toombs","Towns","Treutlen",
      "Troup","Turner","Twiggs","Union","Upson","Walker","Walton","Ware","Warren",
      "Washington","Wayne","Webster","Wheeler","White","Whitfield","Wilcox","Wilkes",
      "Wilkinson","Worth"],
    Florida: ["Alachua","Baker","Bay","Bradford","Brevard","Broward","Calhoun","Charlotte","Citrus",
      "Clay","Collier","Columbia","DeSoto","Dixie","Duval","Escambia","Flagler","Franklin",
      "Gadsden","Gilchrist","Glades","Gulf","Hamilton","Hardee","Hendry","Hernando",
      "Highlands","Hillsborough","Holmes","Indian River","Jackson","Jefferson","Lafayette",
      "Lake","Lee","Leon","Levy","Liberty","Madison","Manatee","Marion","Martin",
      "Miami-Dade","Monroe","Nassau","Okaloosa","Okeechobee","Orange","Osceola",
      "Palm Beach","Pasco","Pinellas","Polk","Putnam","Santa Rosa","Sarasota","Seminole",
      "St. Johns","St. Lucie","Sumter","Suwannee","Taylor","Union","Volusia","Wakulla",
      "Walton","Washington"],
    Alabama: ["Autauga","Baldwin","Barbour","Bibb","Blount","Bullock","Butler","Calhoun","Chambers",
      "Cherokee","Chilton","Choctaw","Clarke","Clay","Cleburne","Coffee","Colbert",
      "Conecuh","Coosa","Covington","Crenshaw","Cullman","Dale","Dallas","DeKalb","Elmore",
      "Escambia","Etowah","Fayette","Franklin","Geneva","Greene","Hale","Henry","Houston",
      "Jackson","Jefferson","Lamar","Lauderdale","Lawrence","Lee","Limestone","Lowndes",
      "Macon","Madison","Marengo","Marion","Marshall","Mobile","Monroe","Montgomery",
      "Morgan","Perry","Pickens","Pike","Randolph","Russell","Shelby","St. Clair","Sumter",
      "Talladega","Tallapoosa","Tuscaloosa","Walker","Washington","Wilcox","Winston"],
    Mississippi: ["Adams","Alcorn","Amite","Attala","Benton","Bolivar","Calhoun","Carroll","Chickasaw",
      "Choctaw","Claiborne","Clarke","Clay","Coahoma","Copiah","Covington","DeSoto",
      "Forrest","Franklin","George","Greene","Grenada","Hancock","Harrison","Hinds",
      "Holmes","Humphreys","Issaquena","Itawamba","Jackson","Jasper","Jefferson",
      "Jefferson Davis","Jones","Kemper","Lafayette","Lamar","Lauderdale","Lawrence",
      "Leake","Lee","Leflore","Lincoln","Lowndes","Madison","Marion","Marshall","Monroe",
      "Montgomery","Neshoba","Newton","Noxubee","Oktibbeha","Panola","Pearl River","Perry",
      "Pike","Pontotoc","Prentiss","Quitman","Rankin","Scott","Sharkey","Simpson","Smith",
      "Stone","Sunflower","Tallahatchie","Tate","Tippah","Tishomingo","Tunica","Union",
      "Walthall","Warren","Washington","Wayne","Webster","Wilkinson","Winston","Yalobusha",
      "Yazoo"],
    Tennessee: ["Anderson","Bedford","Benton","Bledsoe","Blount","Bradley","Campbell","Cannon",
      "Carroll","Carter","Cheatham","Chester","Claiborne","Clay","Cocke","Coffee",
      "Crockett","Cumberland","Davidson","DeKalb","Decatur","Dickson","Dyer","Fayette",
      "Fentress","Franklin","Gibson","Giles","Grainger","Greene","Grundy","Hamblen",
      "Hamilton","Hancock","Hardeman","Hardin","Hawkins","Haywood","Henderson","Henry",
      "Hickman","Houston","Humphreys","Jackson","Jefferson","Johnson","Knox","Lake",
      "Lauderdale","Lawrence","Lewis","Lincoln","Loudon","Macon","Madison","Marion",
      "Marshall","Maury","McMinn","McNairy","Meigs","Monroe","Montgomery","Moore","Morgan",
      "Obion","Overton","Perry","Pickett","Polk","Putnam","Rhea","Roane","Robertson",
      "Rutherford","Scott","Sequatchie","Sevier","Shelby","Smith","Stewart","Sullivan",
      "Sumner","Tipton","Trousdale","Unicoi","Union","Van Buren","Warren","Washington",
      "Wayne","Weakley","White","Williamson","Wilson"],
    Kentucky: ["Adair","Allen","Anderson","Ballard","Barren","Bath","Bell","Boone","Bourbon","Boyd",
      "Boyle","Bracken","Breathitt","Breckinridge","Bullitt","Butler","Caldwell","Calloway",
      "Campbell","Carlisle","Carroll","Carter","Casey","Christian","Clark","Clay","Clinton",
      "Crittenden","Cumberland","Daviess","Edmonson","Elliott","Estill","Fayette","Fleming",
      "Floyd","Franklin","Fulton","Gallatin","Garrard","Grant","Graves","Grayson","Green",
      "Greenup","Hancock","Hardin","Harlan","Harrison","Hart","Henderson","Henry","Hickman",
      "Hopkins","Jackson","Jefferson","Jessamine","Johnson","Kenton","Knott","Knox","Larue",
      "Laurel","Lawrence","Lee","Leslie","Letcher","Lewis","Lincoln","Livingston","Logan",
      "Lyon","Madison","Magoffin","Marion","Marshall","Martin","Mason","McCracken",
      "McCreary","McLean","Meade","Menifee","Mercer","Metcalfe","Monroe","Montgomery",
      "Morgan","Muhlenberg","Nelson","Nicholas","Ohio","Oldham","Owen","Owsley","Pendleton",
      "Perry","Pike","Powell","Pulaski","Robertson","Rockcastle","Rowan","Russell","Scott",
      "Shelby","Simpson","Spencer","Taylor","Todd","Trigg","Trimble","Union","Warren",
      "Washington","Wayne","Webster","Whitley","Wolfe","Woodford"],
    Ohio: ["Adams","Allen","Ashland","Ashtabula","Athens","Auglaize","Belmont","Brown","Butler",
      "Carroll","Champaign","Clark","Clermont","Clinton","Columbiana","Coshocton",
      "Crawford","Cuyahoga","Darke","Defiance","Delaware","Erie","Fairfield","Fayette",
      "Franklin","Fulton","Gallia","Geauga","Greene","Guernsey","Hamilton","Hancock",
      "Hardin","Harrison","Henry","Highland","Hocking","Holmes","Huron","Jackson",
      "Jefferson","Knox","Lake","Lawrence","Licking","Logan","Lorain","Lucas","Madison",
      "Mahoning","Marion","Medina","Meigs","Mercer","Miami","Monroe","Montgomery","Morgan",
      "Morrow","Muskingum","Noble","Ottawa","Paulding","Perry","Pickaway","Pike","Portage",
      "Preble","Putnam","Richland","Ross","Sandusky","Scioto","Seneca","Shelby","Stark",
      "Summit","Trumbull","Tuscarawas","Union","Van Wert","Vinton","Warren","Washington",
      "Wayne","Williams","Wood","Wyandot"],
    Indiana: ["Adams","Allen","Bartholomew","Benton","Blackford","Boone","Brown","Carroll","Cass",
      "Clark","Clay","Clinton","Crawford","Daviess","DeKalb","Dearborn","Decatur",
      "Delaware","Dubois","Elkhart","Fayette","Floyd","Fountain","Franklin","Fulton",
      "Gibson","Grant","Greene","Hamilton","Hancock","Harrison","Hendricks","Henry",
      "Howard","Huntington","Jackson","Jasper","Jay","Jefferson","Jennings","Johnson",
      "Knox","Kosciusko","LaGrange","LaPorte","Lake","Lawrence","Madison","Marion",
      "Marshall","Martin","Miami","Monroe","Montgomery","Morgan","Newton","Noble","Ohio",
      "Orange","Owen","Parke","Perry","Pike","Porter","Posey","Pulaski","Putnam","Randolph",
      "Ripley","Rush","Scott","Shelby","Spencer","St. Joseph","Starke","Steuben","Sullivan",
      "Switzerland","Tippecanoe","Tipton","Union","Vanderburgh","Vermillion","Vigo",
      "Wabash","Warren","Warrick","Washington","Wayne","Wells","White","Whitley"],
    Illinois: ["Adams","Alexander","Bond","Boone","Brown","Bureau","Calhoun","Carroll","Cass",
      "Champaign","Christian","Clark","Clay","Clinton","Coles","Cook","Crawford",
      "Cumberland","De Witt","DeKalb","Douglas","DuPage","Edgar","Edwards","Effingham",
      "Fayette","Ford","Franklin","Fulton","Gallatin","Greene","Grundy","Hamilton",
      "Hancock","Hardin","Henderson","Henry","Iroquois","Jackson","Jasper","Jefferson",
      "Jersey","Jo Daviess","Johnson","Kane","Kankakee","Kendall","Knox","LaSalle","Lake",
      "Lawrence","Lee","Livingston","Logan","Macon","Macoupin","Madison","Marion",
      "Marshall","Mason","Massac","McDonough","McHenry","McLean","Menard","Mercer","Monroe",
      "Montgomery","Morgan","Moultrie","Ogle","Peoria","Perry","Piatt","Pike","Pope",
      "Pulaski","Putnam","Randolph","Richland","Rock Island","Saline","Sangamon","Schuyler",
      "Scott","Shelby","St. Clair","Stark","Stephenson","Tazewell","Union","Vermilion",
      "Wabash","Warren","Washington","Wayne","White","Whiteside","Will","Williamson",
      "Winnebago","Woodford"],
    Michigan: ["Alcona","Alger","Allegan","Alpena","Antrim","Arenac","Baraga","Barry","Bay","Benzie",
      "Berrien","Branch","Calhoun","Cass","Charlevoix","Cheboygan","Chippewa","Clare",
      "Clinton","Crawford","Delta","Dickinson","Eaton","Emmet","Genesee","Gladwin",
      "Gogebic","Grand Traverse","Gratiot","Hillsdale","Houghton","Huron","Ingham","Ionia",
      "Iosco","Iron","Isabella","Jackson","Kalamazoo","Kalkaska","Kent","Keweenaw","Lake",
      "Lapeer","Leelanau","Lenawee","Livingston","Luce","Mackinac","Macomb","Manistee",
      "Marquette","Mason","Mecosta","Menominee","Midland","Missaukee","Monroe","Montcalm",
      "Montmorency","Muskegon","Newaygo","Oakland","Oceana","Ogemaw","Ontonagon","Osceola",
      "Oscoda","Otsego","Ottawa","Presque Isle","Roscommon","Saginaw","Sanilac",
      "Schoolcraft","Shiawassee","St. Clair","St. Joseph","Tuscola","Van Buren","Washtenaw",
      "Wayne","Wexford"],
    Wisconsin: ["Adams","Ashland","Barron","Bayfield","Brown","Buffalo","Burnett","Calumet",
      "Chippewa","Clark","Columbia","Crawford","Dane","Dodge","Door","Douglas","Dunn",
      "Eau Claire","Florence","Fond du Lac","Forest","Grant","Green","Green Lake","Iowa",
      "Iron","Jackson","Jefferson","Juneau","Kenosha","Kewaunee","La Crosse","Lafayette",
      "Langlade","Lincoln","Manitowoc","Marathon","Marinette","Marquette","Menominee",
      "Milwaukee","Monroe","Oconto","Oneida","Outagamie","Ozaukee","Pepin","Pierce","Polk",
      "Portage","Price","Racine","Richland","Rock","Rusk","Sauk","Sawyer","Shawano",
      "Sheboygan","St. Croix","Taylor","Trempealeau","Vernon","Vilas","Walworth","Washburn",
      "Washington","Waukesha","Waupaca","Waushara","Winnebago","Wood"],
    Minnesota: ["Aitkin","Anoka","Becker","Beltrami","Benton","Big Stone","Blue Earth","Brown",
      "Carlton","Carver","Cass","Chippewa","Chisago","Clay","Clearwater","Cook",
      "Cottonwood","Crow Wing","Dakota","Dodge","Douglas","Faribault","Fillmore","Freeborn",
      "Goodhue","Grant","Hennepin","Houston","Hubbard","Isanti","Itasca","Jackson",
      "Kanabec","Kandiyohi","Kittson","Koochiching","Lac qui Parle","Lake",
      "Lake of the Woods","Le Sueur","Lincoln","Lyon","Mahnomen","Marshall","Martin",
      "McLeod","Meeker","Mille Lacs","Morrison","Mower","Murray","Nicollet","Nobles",
      "Norman","Olmsted","Otter Tail","Pennington","Pine","Pipestone","Polk","Pope",
      "Ramsey","Red Lake","Redwood","Renville","Rice","Rock","Roseau","Scott","Sherburne",
      "Sibley","St. Louis","Stearns","Steele","Stevens","Swift","Todd","Traverse","Wabasha",
      "Wadena","Waseca","Washington","Watonwan","Wilkin","Winona","Wright",
      "Yellow Medicine"],
    Iowa: ["Adair","Adams","Allamakee","Appanoose","Audubon","Benton","Black Hawk","Boone",
      "Bremer","Buchanan","Buena Vista","Butler","Calhoun","Carroll","Cass","Cedar",
      "Cerro Gordo","Cherokee","Chickasaw","Clarke","Clay","Clayton","Clinton","Crawford",
      "Dallas","Davis","Decatur","Delaware","Des Moines","Dickinson","Dubuque","Emmet",
      "Fayette","Floyd","Franklin","Fremont","Greene","Grundy","Guthrie","Hamilton",
      "Hancock","Hardin","Harrison","Henry","Howard","Humboldt","Ida","Iowa","Jackson",
      "Jasper","Jefferson","Johnson","Jones","Keokuk","Kossuth","Lee","Linn","Louisa",
      "Lucas","Lyon","Madison","Mahaska","Marion","Marshall","Mills","Mitchell","Monona",
      "Monroe","Montgomery","Muscatine","O'Brien","Osceola","Page","Palo Alto","Plymouth",
      "Pocahontas","Polk","Pottawattamie","Poweshiek","Ringgold","Sac","Scott","Shelby",
      "Sioux","Story","Tama","Taylor","Union","Van Buren","Wapello","Warren","Washington",
      "Wayne","Webster","Winnebago","Winneshiek","Woodbury","Worth","Wright"],
    Missouri: ["Adair","Andrew","Atchison","Audrain","Barry","Barton","Bates","Benton","Bollinger",
      "Boone","Buchanan","Butler","Caldwell","Callaway","Camden","Cape Girardeau","Carroll",
      "Carter","Cass","Cedar","Chariton","Christian","Clark","Clay","Clinton","Cole",
      "Cooper","Crawford","Dade","Dallas","Daviess","DeKalb","Dent","Douglas","Dunklin",
      "Franklin","Gasconade","Gentry","Greene","Grundy","Harrison","Henry","Hickory","Holt",
      "Howard","Howell","Iron","Jackson","Jasper","Jefferson","Johnson","Knox","Laclede",
      "Lafayette","Lawrence","Lewis","Lincoln","Linn","Livingston","Macon","Madison",
      "Maries","Marion","McDonald","Mercer","Miller","Mississippi","Moniteau","Monroe",
      "Montgomery","Morgan","New Madrid","Newton","Nodaway","Oregon","Osage","Ozark",
      "Pemiscot","Perry","Pettis","Phelps","Pike","Platte","Polk","Pulaski","Putnam",
      "Ralls","Randolph","Ray","Reynolds","Ripley","Saline","Schuyler","Scotland","Scott",
      "Shannon","Shelby","St. Charles","St. Clair","St. Francois","St. Louis","St. Louis",
      "Ste. Genevieve","Stoddard","Stone","Sullivan","Taney","Texas","Vernon","Warren",
      "Washington","Wayne","Webster","Worth","Wright"],
    Arkansas: ["Arkansas","Ashley","Baxter","Benton","Boone","Bradley","Calhoun","Carroll","Chicot",
      "Clark","Clay","Cleburne","Cleveland","Columbia","Conway","Craighead","Crawford",
      "Crittenden","Cross","Dallas","Desha","Drew","Faulkner","Franklin","Fulton","Garland",
      "Grant","Greene","Hempstead","Hot Spring","Howard","Independence","Izard","Jackson",
      "Jefferson","Johnson","Lafayette","Lawrence","Lee","Lincoln","Little River","Logan",
      "Lonoke","Madison","Marion","Miller","Mississippi","Monroe","Montgomery","Nevada",
      "Newton","Ouachita","Perry","Phillips","Pike","Poinsett","Polk","Pope","Prairie",
      "Pulaski","Randolph","Saline","Scott","Searcy","Sebastian","Sevier","Sharp",
      "St. Francis","Stone","Union","Van Buren","Washington","White","Woodruff","Yell"],
    Louisiana: ["Acadia","Allen","Ascension","Assumption","Avoyelles","Beauregard","Bienville",
      "Bossier","Caddo","Calcasieu","Caldwell","Cameron","Catahoula","Claiborne",
      "Concordia","De Soto","East Baton Rouge","East Carroll","East Feliciana","Evangeline",
      "Franklin","Grant","Iberia","Iberville","Jackson","Jefferson","Jefferson Davis",
      "LaSalle","Lafayette","Lafourche","Lincoln","Livingston","Madison","Morehouse",
      "Natchitoches","Orleans","Ouachita","Plaquemines","Pointe Coupee","Rapides",
      "Red River","Richland","Sabine","St. Bernard","St. Charles","St. Helena","St. James",
      "St. John the Baptist","St. Landry","St. Martin","St. Mary","St. Tammany",
      "Tangipahoa","Tensas","Terrebonne","Union","Vermilion","Vernon","Washington",
      "Webster","West Baton Rouge","West Carroll","West Feliciana","Winn"],
    "North Dakota": ["Adams","Barnes","Benson","Billings","Bottineau","Bowman","Burke","Burleigh","Cass",
      "Cavalier","Dickey","Divide","Dunn","Eddy","Emmons","Foster","Golden Valley",
      "Grand Forks","Grant","Griggs","Hettinger","Kidder","LaMoure","Logan","McHenry",
      "McIntosh","McKenzie","McLean","Mercer","Morton","Mountrail","Nelson","Oliver",
      "Pembina","Pierce","Ramsey","Ransom","Renville","Richland","Rolette","Sargent",
      "Sheridan","Sioux","Slope","Stark","Steele","Stutsman","Towner","Traill","Walsh",
      "Ward","Wells","Williams"],
    "South Dakota": ["Aurora","Beadle","Bennett","Bon Homme","Brookings","Brown","Brule","Buffalo","Butte",
      "Campbell","Charles Mix","Clark","Clay","Codington","Corson","Custer","Davison","Day",
      "Deuel","Dewey","Douglas","Edmunds","Fall River","Faulk","Grant","Gregory","Haakon",
      "Hamlin","Hand","Hanson","Harding","Hughes","Hutchinson","Hyde","Jackson","Jerauld",
      "Jones","Kingsbury","Lake","Lawrence","Lincoln","Lyman","Marshall","McCook",
      "McPherson","Meade","Mellette","Miner","Minnehaha","Moody","Oglala Lakota",
      "Pennington","Perkins","Potter","Roberts","Sanborn","Spink","Stanley","Sully","Todd",
      "Tripp","Turner","Union","Walworth","Yankton","Ziebach"],
    Nebraska: ["Adams","Antelope","Arthur","Banner","Blaine","Boone","Box Butte","Boyd","Brown",
      "Buffalo","Burt","Butler","Cass","Cedar","Chase","Cherry","Cheyenne","Clay","Colfax",
      "Cuming","Custer","Dakota","Dawes","Dawson","Deuel","Dixon","Dodge","Douglas","Dundy",
      "Fillmore","Franklin","Frontier","Furnas","Gage","Garden","Garfield","Gosper","Grant",
      "Greeley","Hall","Hamilton","Harlan","Hayes","Hitchcock","Holt","Hooker","Howard",
      "Jefferson","Johnson","Kearney","Keith","Keya Paha","Kimball","Knox","Lancaster",
      "Lincoln","Logan","Loup","Madison","McPherson","Merrick","Morrill","Nance","Nemaha",
      "Nuckolls","Otoe","Pawnee","Perkins","Phelps","Pierce","Platte","Polk","Red Willow",
      "Richardson","Rock","Saline","Sarpy","Saunders","Scotts Bluff","Seward","Sheridan",
      "Sherman","Sioux","Stanton","Thayer","Thomas","Thurston","Valley","Washington",
      "Wayne","Webster","Wheeler","York"],
    Kansas: ["Allen","Anderson","Atchison","Barber","Barton","Bourbon","Brown","Butler","Chase",
      "Chautauqua","Cherokee","Cheyenne","Clark","Clay","Cloud","Coffey","Comanche",
      "Cowley","Crawford","Decatur","Dickinson","Doniphan","Douglas","Edwards","Elk",
      "Ellis","Ellsworth","Finney","Ford","Franklin","Geary","Gove","Graham","Grant","Gray",
      "Greeley","Greenwood","Hamilton","Harper","Harvey","Haskell","Hodgeman","Jackson",
      "Jefferson","Jewell","Johnson","Kearny","Kingman","Kiowa","Labette","Lane",
      "Leavenworth","Lincoln","Linn","Logan","Lyon","Marion","Marshall","McPherson","Meade",
      "Miami","Mitchell","Montgomery","Morris","Morton","Nemaha","Neosho","Ness","Norton",
      "Osage","Osborne","Ottawa","Pawnee","Phillips","Pottawatomie","Pratt","Rawlins",
      "Reno","Republic","Rice","Riley","Rooks","Rush","Russell","Saline","Scott","Sedgwick",
      "Seward","Shawnee","Sheridan","Sherman","Smith","Stafford","Stanton","Stevens",
      "Sumner","Thomas","Trego","Wabaunsee","Wallace","Washington","Wichita","Wilson",
      "Woodson","Wyandotte"],
    Oklahoma: ["Adair","Alfalfa","Atoka","Beaver","Beckham","Blaine","Bryan","Caddo","Canadian",
      "Carter","Cherokee","Choctaw","Cimarron","Cleveland","Coal","Comanche","Cotton",
      "Craig","Creek","Custer","Delaware","Dewey","Ellis","Garfield","Garvin","Grady",
      "Grant","Greer","Harmon","Harper","Haskell","Hughes","Jackson","Jefferson","Johnston",
      "Kay","Kingfisher","Kiowa","Latimer","Le Flore","Lincoln","Logan","Love","Major",
      "Marshall","Mayes","McClain","McCurtain","McIntosh","Murray","Muskogee","Noble",
      "Nowata","Okfuskee","Oklahoma","Okmulgee","Osage","Ottawa","Pawnee","Payne",
      "Pittsburg","Pontotoc","Pottawatomie","Pushmataha","Roger Mills","Rogers","Seminole",
      "Sequoyah","Stephens","Texas","Tillman","Tulsa","Wagoner","Washington","Washita",
      "Woods","Woodward"],
    Texas: ["Anderson","Andrews","Angelina","Aransas","Archer","Armstrong","Atascosa","Austin",
      "Bailey","Bandera","Bastrop","Baylor","Bee","Bell","Bexar","Blanco","Borden","Bosque",
      "Bowie","Brazoria","Brazos","Brewster","Briscoe","Brooks","Brown","Burleson","Burnet",
      "Caldwell","Calhoun","Callahan","Cameron","Camp","Carson","Cass","Castro","Chambers",
      "Cherokee","Childress","Clay","Cochran","Coke","Coleman","Collin","Collingsworth",
      "Colorado","Comal","Comanche","Concho","Cooke","Coryell","Cottle","Crane","Crockett",
      "Crosby","Culberson","Dallam","Dallas","Dawson","DeWitt","Deaf Smith","Delta",
      "Denton","Dickens","Dimmit","Donley","Duval","Eastland","Ector","Edwards","El Paso",
      "Ellis","Erath","Falls","Fannin","Fayette","Fisher","Floyd","Foard","Fort Bend",
      "Franklin","Freestone","Frio","Gaines","Galveston","Garza","Gillespie","Glasscock",
      "Goliad","Gonzales","Gray","Grayson","Gregg","Grimes","Guadalupe","Hale","Hall",
      "Hamilton","Hansford","Hardeman","Hardin","Harris","Harrison","Hartley","Haskell",
      "Hays","Hemphill","Henderson","Hidalgo","Hill","Hockley","Hood","Hopkins","Houston",
      "Howard","Hudspeth","Hunt","Hutchinson","Irion","Jack","Jackson","Jasper",
      "Jeff Davis","Jefferson","Jim Hogg","Jim Wells","Johnson","Jones","Karnes","Kaufman",
      "Kendall","Kenedy","Kent","Kerr","Kimble","King","Kinney","Kleberg","Knox","La Salle",
      "Lamar","Lamb","Lampasas","Lavaca","Lee","Leon","Liberty","Limestone","Lipscomb",
      "Live Oak","Llano","Loving","Lubbock","Lynn","Madison","Marion","Martin","Mason",
      "Matagorda","Maverick","McCulloch","McLennan","McMullen","Medina","Menard","Midland",
      "Milam","Mills","Mitchell","Montague","Montgomery","Moore","Morris","Motley",
      "Nacogdoches","Navarro","Newton","Nolan","Nueces","Ochiltree","Oldham","Orange",
      "Palo Pinto","Panola","Parker","Parmer","Pecos","Polk","Potter","Presidio","Rains",
      "Randall","Reagan","Real","Red River","Reeves","Refugio","Roberts","Robertson",
      "Rockwall","Runnels","Rusk","Sabine","San Augustine","San Jacinto","San Patricio",
      "San Saba","Schleicher","Scurry","Shackelford","Shelby","Sherman","Smith","Somervell",
      "Starr","Stephens","Sterling","Stonewall","Sutton","Swisher","Tarrant","Taylor",
      "Terrell","Terry","Throckmorton","Titus","Tom Green","Travis","Trinity","Tyler",
      "Upshur","Upton","Uvalde","Val Verde","Van Zandt","Victoria","Walker","Waller","Ward",
      "Washington","Webb","Wharton","Wheeler","Wichita","Wilbarger","Willacy","Williamson",
      "Wilson","Winkler","Wise","Wood","Yoakum","Young","Zapata","Zavala"],
    Montana: ["Beaverhead","Big Horn","Blaine","Broadwater","Carbon","Carter","Cascade","Chouteau",
      "Custer","Daniels","Dawson","Deer Lodge","Fallon","Fergus","Flathead","Gallatin",
      "Garfield","Glacier","Golden Valley","Granite","Hill","Jefferson","Judith Basin",
      "Lake","Lewis and Clark","Liberty","Lincoln","Madison","McCone","Meagher","Mineral",
      "Missoula","Musselshell","Park","Petroleum","Phillips","Pondera","Powder River",
      "Powell","Prairie","Ravalli","Richland","Roosevelt","Rosebud","Sanders","Sheridan",
      "Silver Bow","Stillwater","Sweet Grass","Teton","Toole","Treasure","Valley",
      "Wheatland","Wibaux","Yellowstone"],
    Idaho: ["Ada","Adams","Bannock","Bear Lake","Benewah","Bingham","Blaine","Boise","Bonner",
      "Bonneville","Boundary","Butte","Camas","Canyon","Caribou","Cassia","Clark",
      "Clearwater","Custer","Elmore","Franklin","Fremont","Gem","Gooding","Idaho",
      "Jefferson","Jerome","Kootenai","Latah","Lemhi","Lewis","Lincoln","Madison",
      "Minidoka","Nez Perce","Oneida","Owyhee","Payette","Power","Shoshone","Teton",
      "Twin Falls","Valley","Washington"],
    Wyoming: ["Albany","Big Horn","Campbell","Carbon","Converse","Crook","Fremont","Goshen",
      "Hot Springs","Johnson","Laramie","Lincoln","Natrona","Niobrara","Park","Platte",
      "Sheridan","Sublette","Sweetwater","Teton","Uinta","Washakie","Weston"],
    Nevada: ["Carson City","Churchill","Clark","Douglas","Elko","Esmeralda","Eureka","Humboldt",
      "Lander","Lincoln","Lyon","Mineral","Nye","Pershing","Storey","Washoe","White Pine"],
    Utah: ["Beaver","Box Elder","Cache","Carbon","Daggett","Davis","Duchesne","Emery","Garfield",
      "Grand","Iron","Juab","Kane","Millard","Morgan","Piute","Rich","Salt Lake","San Juan",
      "Sanpete","Sevier","Summit","Tooele","Uintah","Utah","Wasatch","Washington","Wayne",
      "Weber"],
    Colorado: ["Adams","Alamosa","Arapahoe","Archuleta","Baca","Bent","Boulder","Broomfield",
      "Chaffee","Cheyenne","Clear Creek","Conejos","Costilla","Crowley","Custer","Delta",
      "Denver","Dolores","Douglas","Eagle","El Paso","Elbert","Fremont","Garfield","Gilpin",
      "Grand","Gunnison","Hinsdale","Huerfano","Jackson","Jefferson","Kiowa","Kit Carson",
      "La Plata","Lake","Larimer","Las Animas","Lincoln","Logan","Mesa","Mineral","Moffat",
      "Montezuma","Montrose","Morgan","Otero","Ouray","Park","Phillips","Pitkin","Prowers",
      "Pueblo","Rio Blanco","Rio Grande","Routt","Saguache","San Juan","San Miguel",
      "Sedgwick","Summit","Teller","Washington","Weld","Yuma"],
    Arizona: ["Apache","Cochise","Coconino","Gila","Graham","Greenlee","La Paz","Maricopa","Mohave",
      "Navajo","Pima","Pinal","Santa Cruz","Yavapai","Yuma"],
    "New Mexico": ["Bernalillo","Catron","Chaves","Cibola","Colfax","Curry","De Baca","Doña Ana","Eddy",
      "Grant","Guadalupe","Harding","Hidalgo","Lea","Lincoln","Los Alamos","Luna",
      "McKinley","Mora","Otero","Quay","Rio Arriba","Roosevelt","San Juan","San Miguel",
      "Sandoval","Santa Fe","Sierra","Socorro","Taos","Torrance","Union","Valencia"],
    Oregon: ["Baker","Benton","Clackamas","Clatsop","Columbia","Coos","Crook","Curry","Deschutes",
      "Douglas","Gilliam","Grant","Harney","Hood River","Jackson","Jefferson","Josephine",
      "Klamath","Lake","Lane","Lincoln","Linn","Malheur","Marion","Morrow","Multnomah",
      "Polk","Sherman","Tillamook","Umatilla","Union","Wallowa","Wasco","Washington",
      "Wheeler","Yamhill"],
    Washington: ["Adams","Asotin","Benton","Chelan","Clallam","Clark","Columbia","Cowlitz","Douglas",
      "Ferry","Franklin","Garfield","Grant","Grays Harbor","Island","Jefferson","King",
      "Kitsap","Kittitas","Klickitat","Lewis","Lincoln","Mason","Okanogan","Pacific",
      "Pend Oreille","Pierce","San Juan","Skagit","Skamania","Snohomish","Spokane",
      "Stevens","Thurston","Wahkiakum","Walla Walla","Whatcom","Whitman","Yakima"],
    California: ["Alameda","Alpine","Amador","Butte","Calaveras","Colusa","Contra Costa","Del Norte",
      "El Dorado","Fresno","Glenn","Humboldt","Imperial","Inyo","Kern","Kings","Lake",
      "Lassen","Los Angeles","Madera","Marin","Mariposa","Mendocino","Merced","Modoc",
      "Mono","Monterey","Napa","Nevada","Orange","Placer","Plumas","Riverside","Sacramento",
      "San Benito","San Bernardino","San Diego","San Francisco","San Joaquin",
      "San Luis Obispo","San Mateo","Santa Barbara","Santa Clara","Santa Cruz","Shasta",
      "Sierra","Siskiyou","Solano","Sonoma","Stanislaus","Sutter","Tehama","Trinity",
      "Tulare","Tuolumne","Ventura","Yolo","Yuba"],
    Hawaii: ["Hawaii","Honolulu","Kalawao","Kauai","Maui"],
    Alaska: ["Aleutians East","Aleutians West","Anchorage","Bethel","Bristol Bay","Chugach",
      "Copper River","Denali","Dillingham","Fairbanks North Star","Haines","Hoonah-Angoon",
      "Juneau","Kenai Peninsula","Ketchikan Gateway","Kodiak Island","Kusilvak",
      "Lake and Peninsula","Matanuska-Susitna","Nome","North Slope","Northwest Arctic",
      "Petersburg","Prince of Wales-Hyder","Sitka","Skagway","Southeast Fairbanks",
      "Wrangell","Yakutat","Yukon-Koyukuk"],
  };



  // Palettes. `neon` is the one shipped in src/coloring.PALETTES (config allows
  // only "neon" today); the rest are experimental UX proposals.
  const PALETTES = {
    neon:   ["#00ffff","#0a5cff","#4b0082","#9d00ff","#8f00ff","#ff00ff","#ff7a00","#ffd700","#aaff00","#00ffab","#00e0d1","#00ff5f"],
    aurora: ["#00ff9c","#00e0d1","#38b6ff","#5a7bff","#7a5cff","#00ffab","#2fffd0","#66ffcc","#3fa9ff","#8f7bff","#00d4a0","#41e0ff"],
    ember:  ["#ff3b00","#ff7a00","#ffb300","#ffd700","#ff5e3a","#ff2d55","#e0004d","#ff9c3a","#ffcf5e","#c41e3a","#ff6f61","#ffae42"],
    ice:    ["#e6ffff","#a8f0ff","#66d9ff","#38b6ff","#5a7bff","#b3ecff","#7fe3ff","#4fb0ff","#cfefff","#89cfff","#6fd7ff","#9fd8ff"],
  };
  // Hypsometric ramp for the "elevation" color mode (white summit -> deep-blue
  // sea), mirroring tools/render_state_mono.py.
  const HYPSO = ["#ffffff","#dff0ff","#a8d8ff","#66b6ff","#3f8fe6","#2f6bc4","#1f4a9c","#123a7a","#0a2a5c","#06213f"];

  // src/monthly_flow.MONTH_ABBR (and src/config parses these names in --months).
  const MONTH_ABBR = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  // src/config.SUPPORTED_HUC_LEVELS.
  const HUC_LEVELS = ["HUC2","HUC4","HUC6","HUC8","HUC10","HUC12"];

  // ---- Deterministic PRNG (so previews are reproducible per seed) ----------
  function mulberry32(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
  function hash(str){let h=2166136261;for(let i=0;i<str.length;i++){h^=str.charCodeAt(i);h=Math.imul(h,16777619);}return h>>>0;}

  // ---- Procedural network model -------------------------------------------
  // net = { basins:[{segs:[{pts,flow,children,phase,elev}]}], maxFlow, viewBox, unitScale }
  const VB = { w: 1000, h: 1177 };

  function generateNetwork(seed, nBasins){
    nBasins = nBasins || 6;
    const rnd = mulberry32(seed);
    const basins = Array.from({length: nBasins}, () => ({ segs: [] }));
    const rootX = 500, rootY = 1120, spread = 2.1;
    for (let b = 0; b < nBasins; b++){
      const a0 = -Math.PI/2 - spread/2 + spread*(b+0.5)/nBasins + (rnd()-0.5)*0.15;
      // Each basin gets a seasonal peak month: some snowmelt (spring), some rain (winter).
      basins[b].phase = rnd() < 0.5 ? (3 + rnd()*2) : (11 + rnd()*2) % 12; // 0-based month
      grow(basins[b].segs, rootX, rootY, a0, 250, 10, rnd, basins[b].phase);
    }
    let maxFlow = 1, maxElev = 1;
    for (const basin of basins){
      for (let i = basin.segs.length - 1; i >= 0; i--){
        const s = basin.segs[i];
        s.flow = 1 + s.children.reduce((acc,c)=>acc + c.flow, 0);
        if (s.flow > maxFlow) maxFlow = s.flow;
        if (s.elev > maxElev) maxElev = s.elev;
      }
    }
    return { basins, maxFlow, maxElev, viewBox:{...VB}, unitScale: 1 };
  }

  function grow(out, x, y, ang, len, depth, rnd, phase){
    if (depth <= 0 || len < 6) return null;
    const midJit = (rnd()-0.5) * len * 0.25;
    const nx = x + Math.cos(ang)*len, ny = y + Math.sin(ang)*len;
    const mx = (x+nx)/2 + Math.cos(ang+Math.PI/2)*midJit;
    const my = (y+ny)/2 + Math.sin(ang+Math.PI/2)*midJit;
    // Stylized elevation: headwaters (higher up the tree / lower y) ride high.
    const elev = Math.max(0, (VB.h - ny)) * (0.7 + depth*0.05);
    const seg = { pts: [[x,y],[mx,my],[nx,ny]], children: [], flow: 1, phase, elev };
    out.push(seg);
    const branches = rnd() < 0.78 ? 2 : (rnd() < 0.7 ? 1 : 3);
    const spread = 0.35 + rnd()*0.5;
    for (let k = 0; k < branches; k++){
      const da = branches === 1 ? (rnd()-0.5)*0.4
               : (-spread/2 + spread*(k)/(branches-1)) + (rnd()-0.5)*0.2;
      const child = grow(out, nx, ny, ang + da, len*(0.66+rnd()*0.12), depth-1, rnd, phase);
      if (child) seg.children.push(child);
    }
    return seg;
  }

  // ---- Seasonal monthly-flow simulation (mirrors tools/monthly_flow.py) -----
  // Multiplier in ~[0.35, 1.9] for a basin at a given (0-based) month, peaking at
  // the basin's phase. Deterministic; no real climate data.
  function seasonalMultiplier(month0, phase){
    const amp = 0.55;
    return 1 + amp * Math.cos(2*Math.PI*(month0 - phase)/12);
  }
  // Fixed year-max so a fat January mainstem really looks fatter than August.
  function yearMaxFlow(net){
    let mx = 1;
    for (const b of net.basins) for (const s of b.segs)
      for (let m=0;m<12;m++) mx = Math.max(mx, s.flow * seasonalMultiplier(m, b.phase));
    return mx;
  }

  // ---- SVG builder --------------------------------------------------------
  function dOf(pts){ return "M " + pts.map(p=>p[0].toFixed(1)+","+p[1].toFixed(1)).join(" L "); }

  function buildSvg(net){
    const { basins, viewBox } = net;
    let s = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${viewBox.w} ${viewBox.h}" `
          + `fill="none" stroke-linecap="round" stroke-linejoin="round">`;
    s += `<defs><filter id="glow" x="-20%" y="-20%" width="140%" height="140%">`
       + `<feGaussianBlur id="glowBlur" stdDeviation="0" result="b"/>`
       + `<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>`;
    s += `<rect id="bgRect" x="0" y="0" width="${viewBox.w}" height="${viewBox.h}"/>`;
    basins.forEach((basin, bi) => {
      s += `<g class="basin" data-basin="${bi}">`;
      for (const seg of basin.segs){
        s += `<path data-flow="${seg.flow.toFixed(3)}" data-elev="${(seg.elev||0).toFixed(1)}" d="${dOf(seg.pts)}"/>`;
      }
      s += `</g>`;
    });
    return s + `</svg>`;
  }

  function rampColor(ramp, t){
    t = Math.max(0, Math.min(1, t));
    const x = t * (ramp.length - 1), i = Math.floor(x);
    return ramp[Math.min(ramp.length - 1, i)]; // nearest stop — plenty for a preview
  }

  // ---- Apply a UX `state` onto the live SVG -------------------------------
  // state: { colorMode:'watershed'|'single'|'elevation', palette, single, bg,
  //          widthMode:'flow'|'uniform', minW, maxW, gamma, glow, glowR,
  //          month (0-based, for the currently displayed frame) }
  function applyStyles(svg, net, state){
    if (!svg || !net) return;
    const scale = net.unitScale;
    const pal = PALETTES[state.palette] || PALETTES.neon;
    const yMax = net._yearMax || (net._yearMax = yearMaxFlow(net));
    const month0 = (state.month == null) ? 6 : state.month;

    svg.querySelector("#bgRect").setAttribute("fill", state.bg);
    svg.querySelector("#glowBlur").setAttribute("stdDeviation", state.glow ? (state.glowR*scale).toFixed(2) : "0");

    [...svg.querySelectorAll("g.basin")].forEach((g, bi) => {
      const phase = net.basins[bi].phase;
      const mult = seasonalMultiplier(month0, phase);
      let groupStroke = null;
      if (state.colorMode === "single") groupStroke = state.single;
      else if (state.colorMode === "watershed") groupStroke = pal[bi % pal.length];
      // elevation mode colors per-path below (per-segment), so leave group unset.
      if (groupStroke) g.setAttribute("stroke", groupStroke);
      g.setAttribute("filter", state.glow ? "url(#glow)" : "");

      for (const p of g.querySelectorAll("path")){
        // color
        if (state.colorMode === "elevation"){
          const e = parseFloat(p.getAttribute("data-elev")) / (net.maxElev || 1);
          p.setAttribute("stroke", rampColor(HYPSO, e));
        } else {
          p.removeAttribute("stroke"); // inherit group stroke
        }
        // width
        let wpx;
        if (state.widthMode === "uniform"){
          wpx = state.minW;
        } else {
          const f = parseFloat(p.getAttribute("data-flow")) * mult;
          const t = Math.pow(Math.log(f+1)/Math.log(yMax+1), state.gamma);
          wpx = state.minW + (state.maxW - state.minW) * t;
        }
        p.setAttribute("stroke-width", (wpx*scale).toFixed(3));
      }
    });
  }

  // ---- Mapping: UX selections -> build.py CLI + config.yaml ----------------
  function scopeToken(state){
    if (state.scope === "county" && state.county) return `county:${state.county},${stateAbbr(state.state)}`;
    return `region:${state.state}`;
  }
  function stateAbbr(name){ return {Washington:"WA", Oregon:"OR", California:"CA", Idaho:"ID"}[name] || name; }

  function monthsToken(state){
    if (state.timeMode === "annual") return "annual (mean QAMA)";
    if (state.timeMode === "single") return MONTH_ABBR[state.monthStart] + " (single month)";
    return `${MONTH_ABBR[state.monthStart]}\u2013${MONTH_ABBR[state.monthEnd]} (range \u2192 animation)`;
  }

  // Emits a paste-runnable multi-line command. Roadmap #23 (color_by/width_by),
  // #24 (--county), and #25 (--months) have all SHIPPED, so their flags are now
  // emitted as real `build.py` options (src/cli.py) — no more `(proposed)`
  // markers. Two options are shipped-but-not-yet-rendered by the *2D* pipeline
  // and fail fast in build.py, so they carry an honest caveat note (never an
  // inline comment inside the `\`-continued block, which would break the paste):
  //   - color_by=elevation → needs the DEM subsystem (use tools/render_state_mono.py)
  //   - non-annual --months → parses, but live frames land in #27 (tools/render_monthly.py)
  function cliMapping(state){
    const cmd = [`--region ${state.state}`];
    const notes = [];
    if (state.scope === "county" && state.county)
      cmd.push(`--county "${state.county}"`);
    if (state.huc && state.huc !== "HUC4")
      cmd.push(`--huc-level ${state.huc}`);
    cmd.push(`--color-by ${state.colorMode}`);
    if (state.colorMode === "watershed"){
      cmd.push(`--palette ${state.palette}`);
      if (state.palette !== "neon")
        notes.push(`palette "${state.palette}" is a UX experiment; the pipeline ships only "neon" today.`);
    } else if (state.colorMode === "single"){
      cmd.push(`--single-color ${state.single}`);
    } else if (state.colorMode === "elevation"){
      notes.push("color_by=elevation needs the DEM subsystem; the 2D build.py fails fast (use tools/render_state_mono.py).");
    }
    if (state.widthMode === "flow")
      cmd.push(`--width-by flow --width-min ${state.minW} --width-max ${state.maxW} --width-gamma ${state.gamma}`);
    else
      cmd.push(`--width-by uniform`);
    if (state.timeMode !== "annual"){
      const m = state.timeMode === "single" ? (state.monthStart+1)
              : (state.monthStart+1) + "-" + (state.monthEnd+1);
      cmd.push(`--months ${m}`);
      notes.push("non-annual --months parses but the 2D build.py fails fast; live month frames land in #27 (use tools/render_monthly.py).");
    }
    if (state.glow) cmd.push(`--glow --glow-radius ${state.glowR}`);

    // background + base line width have no CLI flag (config-only) — see YAML.
    let out = ".venv/bin/python build.py \\\n  " + cmd.join(" \\\n  ");
    if (notes.length){
      out += "\n  # notes:";
      for (const n of notes) out += "\n  #   " + n;
    }
    return out;
  }

  function yamlMapping(state){
    const k = s => `<span class="k">${s}</span>`, q = s => `<span class="s">${s}</span>`,
          c = s => `<span class="c">${s}</span>`, nn = s => `<span class="n">${s}</span>`;
    const monthsVal = state.timeMode === "annual" ? "annual"
        : state.timeMode === "single" ? String(state.monthStart+1)
        : (state.monthStart+1) + "-" + (state.monthEnd+1);
    const L = [];
    L.push(c("# config.yaml — from the current studio selection"));
    L.push(`${k("region")}: [${state.state}]`);
    if (state.scope === "county" && state.county)
      L.push(`${k("county")}: ${q('"'+state.county+'"')}`);
    L.push(`${k("huc_level")}: ${state.huc}`);
    L.push(`${k("months")}: ${q('"'+monthsVal+'"')}` +
      (state.timeMode !== "annual" ? `        ${c("# parses; non-annual render lands in #27")}` : ""));
    L.push("");
    L.push(`${k("color_by")}: ${q('"'+state.colorMode+'"')}        ${c("# watershed | single | elevation")}`);
    if (state.colorMode === "watershed")
      L.push(`${k("palette")}: ${state.palette}` +
        (state.palette !== "neon" ? `         ${c("# only 'neon' ships today")}` : ""));
    if (state.colorMode === "single")
      L.push(`${k("single_color")}: ${q('"'+state.single+'"')}`);
    if (state.colorMode === "elevation")
      L.push(c("# elevation tint needs the DEM subsystem (fails fast in 2D build.py)"));
    L.push(`${k("background")}: ${q('"'+state.bg+'"')}`);
    L.push("");
    L.push(`${k("width_by")}: ${q('"'+state.widthMode+'"')}       ${c("# uniform | flow")}`);
    L.push(`${k("line_width")}: ${nn(state.minW)}        ${c("# base / uniform stroke")}`);
    if (state.widthMode === "flow"){
      L.push(`${k("width_min")}: ${nn(state.minW)}`);
      L.push(`${k("width_max")}: ${nn(state.maxW)}        ${c("# clamp so rivers stay visible")}`);
      L.push(`${k("width_gamma")}: ${nn(state.gamma)}      ${c("# 0.5≈sqrt spreads small streams")}`);
    }
    L.push("");
    L.push(`${k("glow")}: ${nn(state.glow)}`);
    if (state.glow) L.push(`${k("glow_radius")}: ${nn(state.glowR)}`);
    return L.join("\n");
  }

  // ---- Mapping self-check (determinism + CLI/YAML agreement) ---------------
  // Pure check that the two renderings of one `state` reference the same core
  // selections (region, county, months, color/width modes) and are stable. Used
  // by a headless Node smoke step; returns { ok, issues: [...] }.
  function mappingSelfCheck(state){
    const issues = [];
    const cli = cliMapping(state);
    // YAML carries HTML spans; strip tags for text matching.
    const yaml = yamlMapping(state).replace(/<[^>]+>/g, "");
    const both = (needle, label) => {
      if (!cli.includes(needle)) issues.push(`CLI missing ${label}: ${needle}`);
      if (!yaml.includes(needle)) issues.push(`YAML missing ${label}: ${needle}`);
    };
    both(state.state, "region");
    if (state.scope === "county" && state.county) both(state.county, "county");
    if (state.colorMode !== "watershed") both(state.colorMode, "color_by");
    // Determinism: identical input yields identical text.
    if (cli !== cliMapping(state)) issues.push("cliMapping is non-deterministic");
    if (yamlMapping(state) !== yamlMapping(state)) issues.push("yamlMapping is non-deterministic");
    return { ok: issues.length === 0, issues };
  }

  // ---- Live-run request payload (roadmap #27) ------------------------------
  // Pure function turning the UX `state` into the structured JSON body the local
  // job runner accepts (POST /api/render). These are real `src/config` keys — the
  // server rebuilds Settings through build_settings, so the emitted CLI string is
  // never shell-executed. Mirrors cliMapping's selections exactly.
  function renderRequest(state){
    const months = state.timeMode === "annual" ? "annual"
        : state.timeMode === "single" ? String(state.monthStart+1)
        : (state.monthStart+1) + "-" + (state.monthEnd+1);
    const req = {
      region: state.state,
      huc_level: state.huc,
      months: months,
      color_by: state.colorMode,
      width_by: state.widthMode,
      background: state.bg,
      line_width: state.minW,
      glow: !!state.glow,
    };
    if (state.scope === "county" && state.county) req.county = state.county;
    if (state.colorMode === "watershed") req.palette = state.palette;
    if (state.colorMode === "single") req.single_color = state.single;
    if (state.widthMode === "flow"){
      req.width_min = state.minW; req.width_max = state.maxW; req.width_gamma = state.gamma;
    }
    if (state.glow) req.glow_radius = state.glowR;
    return req;
  }

  // ---- Render recipes & named presets (roadmap #28) -----------------------
  // A *recipe* is the canonical, serializable subset of `state` that captures
  // exactly the reproducible art-direction selections. Preview-only fields
  // (previewSource/loadedName, the derived `month`, the RNG `_nudge`) are NOT
  // part of a recipe. All helpers here are pure/deterministic and file://-safe;
  // studio.html only wires UI to them. Testable headlessly in Node.

  const RECIPE_KEYS = [
    "state", "scope", "county", "huc", "timeMode", "monthStart", "monthEnd",
    "colorMode", "palette", "single", "bg", "widthMode", "minW", "maxW",
    "gamma", "glow", "glowR",
  ];
  const DEFAULT_RECIPE = {
    state: "Oregon", scope: "state", county: null, huc: "HUC4",
    timeMode: "annual", monthStart: 5, monthEnd: 8,
    colorMode: "watershed", palette: "neon", single: "#00e5ff", bg: "#05060a",
    widthMode: "flow", minW: 0.5, maxW: 2.0, gamma: 0.5, glow: false, glowR: 2.5,
  };
  const HEX6 = /^#[0-9a-fA-F]{6}$/;

  function _num(v) { const n = Number(v); return Number.isFinite(n) ? n : null; }
  function _clamp(n, lo, hi) { return Math.min(hi, Math.max(lo, n)); }
  function _isStateId(id) { return STATES.some((s) => s.id === id); }

  // Validate one recipe field independently; returns the accepted value or
  // `undefined` if the input is unusable (caller decides fallback).
  function _validateKey(key, v) {
    switch (key) {
      case "state": return _isStateId(v) ? v : undefined;
      case "scope": return v === "county" ? "county" : (v === "state" ? "state" : undefined);
      case "county": return (v === null || (typeof v === "string" && v.length)) ? v : undefined;
      case "huc": return HUC_LEVELS.includes(v) ? v : undefined;
      case "timeMode": return ["annual", "single", "range"].includes(v) ? v : undefined;
      case "monthStart":
      case "monthEnd": { const n = _num(v); return n === null ? undefined : _clamp(Math.round(n), 0, 11); }
      case "colorMode": return ["watershed", "single", "elevation"].includes(v) ? v : undefined;
      case "palette": return Object.prototype.hasOwnProperty.call(PALETTES, v) ? v : undefined;
      case "single":
      case "bg": return (typeof v === "string" && HEX6.test(v)) ? v : undefined;
      case "widthMode": return ["flow", "uniform"].includes(v) ? v : undefined;
      case "minW": { const n = _num(v); return n === null ? undefined : _clamp(n, 0.05, 10); }
      case "maxW": { const n = _num(v); return n === null ? undefined : _clamp(n, 0.05, 20); }
      case "gamma": { const n = _num(v); return n === null ? undefined : _clamp(n, 0.05, 4); }
      case "glowR": { const n = _num(v); return n === null ? undefined : _clamp(n, 0, 30); }
      case "glow": return Boolean(v);
      default: return undefined;
    }
  }

  // Reconcile county with scope+state so a recipe is always self-consistent.
  function _coherceCounty(rec) {
    if (rec.scope !== "county") { rec.county = null; return rec; }
    const roster = COUNTIES[rec.state] || [];
    if (!roster.includes(rec.county)) rec.county = roster[0] || null;
    return rec;
  }

  // Full sanitize: every key validated/clamped, missing keys filled from
  // DEFAULT_RECIPE, cross-field county/scope coherence enforced. Returns a
  // complete recipe, or null if `obj` is not a usable plain object.
  function sanitizeRecipe(obj) {
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return null;
    const out = Object.assign({}, DEFAULT_RECIPE);
    for (const key of RECIPE_KEYS) {
      if (key === "glow") { out.glow = Boolean(obj.glow); continue; }
      const v = _validateKey(key, obj[key]);
      if (v !== undefined) out[key] = v;
    }
    return _coherceCounty(out);
  }

  // Canonical recipe for a live `state` (drops preview-only fields, sanitizes).
  function toRecipe(state) {
    if (!state || typeof state !== "object") return null;
    const picked = {};
    for (const key of RECIPE_KEYS) picked[key] = state[key];
    return sanitizeRecipe(picked);
  }

  // base64url primitives — btoa/atob in the browser, Buffer in Node, so the
  // round-trip is identical in both and testable headlessly.
  function _b64encode(str) {
    if (typeof btoa === "function") return btoa(unescape(encodeURIComponent(str)));
    return Buffer.from(str, "utf-8").toString("base64");
  }
  function _b64decode(b64) {
    if (typeof atob === "function") return decodeURIComponent(escape(atob(b64)));
    return Buffer.from(b64, "base64").toString("utf-8");
  }
  function b64url(str) {
    return _b64encode(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  function b64urlDecode(s) {
    let t = String(s).replace(/-/g, "+").replace(/_/g, "/");
    while (t.length % 4) t += "=";
    return _b64decode(t);
  }

  function encodeRecipe(state) { return b64url(JSON.stringify(toRecipe(state))); }
  function decodeRecipe(str) {
    try {
      const obj = JSON.parse(b64urlDecode(str));
      return sanitizeRecipe(obj);
    } catch (e) { return null; }
  }

  // Merge a (possibly partial) recipe onto a live state, validating each key
  // that is present. Preview-only fields on `state` are preserved. Absent keys
  // are left untouched (so partial presets only change what they name).
  function applyRecipe(state, recipe) {
    const out = Object.assign({}, state);
    if (recipe && typeof recipe === "object" && !Array.isArray(recipe)) {
      for (const key of RECIPE_KEYS) {
        if (!(key in recipe)) continue;
        const v = _validateKey(key, recipe[key]);
        if (v !== undefined) out[key] = v;
      }
      _coherceCounty(out);
    }
    return out;
  }

  // Named preset catalog. Each `recipe` is a (possibly partial) recipe merged
  // over the current selection. `kind` is a UX grouping hint.
  const PRESETS = [
    { id: "or-screen", label: "Oregon \u00b7 screen", kind: "state",
      recipe: { state: "Oregon", scope: "state", county: null, colorMode: "watershed",
                palette: "neon", widthMode: "flow", glow: false } },
    { id: "clark-print", label: "Clark County \u00b7 print", kind: "county",
      recipe: { state: "Washington", scope: "county", county: "Clark", colorMode: "watershed",
                palette: "ice", widthMode: "uniform", glow: false, bg: "#0a0f14" } },
    { id: "print-mono", label: "Print \u00b7 elevation", kind: "print",
      recipe: { colorMode: "elevation", bg: "#05060a", widthMode: "flow" } },
    { id: "screen-glow", label: "Screen \u00b7 neon glow", kind: "screen",
      recipe: { colorMode: "watershed", palette: "neon", glow: true } },
  ];
  function presetById(id) { return PRESETS.find((p) => p.id === id) || null; }
  function applyPreset(state, id) {
    const p = presetById(id);
    return p ? applyRecipe(state, p.recipe) : Object.assign({}, state);
  }

  // ---- View helpers (DOM; browser-only) -----------------------------------
  // Small helpers shared by the studio + prototype pages so the swatch,
  // month-timeline, county-select, and segmented-control/range view logic lives
  // in one place instead of being copy-pasted per page. They read the already
  // exported option data (PALETTES/COUNTIES/MONTH_ABBR) plus the page's mutable
  // `state`, and write to the fixed element IDs every page shares (#swatches,
  // #county, #timeline, #tlLabel). The event-binding helpers (seg/bindRange)
  // take the page's re-render callback as `after`, since each page repaints
  // differently. `document` is only touched inside the bodies, so this module
  // still loads under Node (the .cjs recipe test never calls these).

  function drawSwatches(state) {
    document.getElementById("swatches").innerHTML =
      PALETTES[state.palette].map((c) => `<i style="background:${c}"></i>`).join("");
  }

  function fillCounties(state) {
    const opts = COUNTIES[state.state];
    document.getElementById("county").innerHTML =
      opts.map((c) => `<option value="${c}">${c}</option>`).join("");
    state.county = opts[0];
  }

  function buildTimeline(state) {
    document.getElementById("timeline").innerHTML =
      MONTH_ABBR.map((m, i) => `<div class="mo" data-m="${i}">${m}</div>`).join("");
    paintTimeline(state);
  }

  function paintTimeline(state) {
    const tl = document.getElementById("timeline");
    [...tl.children].forEach((c, i) => {
      c.classList.remove("in-range", "edge");
      if (state.timeMode === "single" && i === state.monthStart) c.classList.add("edge");
      if (state.timeMode === "range") {
        if (i === state.monthStart || i === state.monthEnd) c.classList.add("edge");
        else if (i > state.monthStart && i < state.monthEnd) c.classList.add("in-range");
      }
    });
    document.getElementById("tlLabel").textContent =
      state.timeMode === "range"
        ? `${MONTH_ABBR[state.monthStart]}\u2013${MONTH_ABBR[state.monthEnd]}`
        : MONTH_ABBR[state.monthStart];
  }

  // Segmented button group: on click, mark the clicked button active, write its
  // `data-v` into `state[key]`, then run `after` (the page's re-render).
  function seg(state, id, key, after) {
    const box = document.getElementById(id);
    box.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      [...box.children].forEach((x) => x.classList.toggle("active", x === b));
      state[key] = b.dataset.v; after();
    });
  }

  // Range input bound to `state[key]` (parsed float); optionally writes a
  // formatted value into `#valId`, then runs `after`.
  function bindRange(state, id, key, fmt, valId, after) {
    document.getElementById(id).addEventListener("input", (e) => {
      state[key] = parseFloat(e.target.value);
      if (valId) document.getElementById(valId).textContent = fmt(state[key]);
      after();
    });
  }

  // ---- Watershed report helpers (#55) — pure formatting + SVG builders ----
  // Node-loadable: no `document`/`window` here, so the headless harness in
  // tests/test_report_helpers.cjs can exercise them. The report page mirrors the
  // offline metrics (src/flow_metrics.py); the web view
  // only *formats* an already-computed report document, it never recomputes.

  // English ordinal ("92" -> "92nd") for percentile-rank labels.
  function ordinal(n) {
    const v = Math.round(n) % 100;
    const s = ["th", "st", "nd", "rd"];
    return `${Math.round(n)}${s[(v - 20) % 10] || s[v] || s[0]}`;
  }

  // Trend glyph from a signed delta: ▲ up, ▼ down, · flat/unknown.
  function trendArrow(delta) {
    if (!isFinite(delta) || delta === 0) return "\u00b7";
    return delta > 0 ? "\u25b2" : "\u25bc";
  }

  // Compact number format (trims a trailing ".0"); keeps small values readable.
  function fmtNum(v, digits) {
    if (!isFinite(v)) return "\u2014";
    digits = digits == null ? (Math.abs(v) >= 100 ? 0 : Math.abs(v) < 1 ? 2 : 1) : digits;
    return Number(v).toFixed(digits).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
  }

  // Map a validation verdict onto the shared status token class used by the CSS
  // (.validation-badge.ok/.warn/.danger and .metric-tile deltas).
  function verdictClass(verdict) {
    return { good: "ok", moderate: "warn", weak: "danger" }[verdict] || "muted";
  }
  function verdictLabel(verdict) {
    return { good: "GOOD", moderate: "MODERATE", weak: "WEAK" }[verdict] || "N/A";
  }

  // Normalize a numeric series to [x,y] points in a w×h box (y inverted so higher
  // values ride up). Non-finite samples are dropped. `pad` insets the stroke so it
  // isn't clipped. Returns [] for an empty/degenerate series.
  function sparklinePoints(values, w, h, pad) {
    pad = pad == null ? 1.5 : pad;
    const xs = [], ys = [];
    (values || []).forEach((v, i) => { if (isFinite(v)) { xs.push(i); ys.push(v); } });
    if (ys.length === 0) return [];
    const n = (values || []).length;
    let lo = Math.min(...ys), hi = Math.max(...ys);
    if (hi === lo) { hi = lo + 1; lo -= 1; } // flat series -> centered line
    const spanX = Math.max(1, n - 1), spanY = hi - lo;
    const iw = w - 2 * pad, ih = h - 2 * pad;
    const pts = [];
    (values || []).forEach((v, i) => {
      if (!isFinite(v)) return;
      pts.push([pad + (i / spanX) * iw, pad + ih - ((v - lo) / spanY) * ih]);
    });
    return pts;
  }

  // An SVG path "d" string ("M x y L x y ...") for a series; "" when empty.
  function sparklinePath(values, w, h, pad) {
    const pts = sparklinePoints(values, w, h, pad);
    if (pts.length === 0) return "";
    return pts.map(([x, y], i) =>
      `${i === 0 ? "M" : "L"}${fmtNum(x, 2)} ${fmtNum(y, 2)}`).join(" ");
  }

  // A self-contained inline <svg> sparkline string (class "sparkline"; the CSS
  // styles path/dot/band). Draws the series line plus a dot on the last point.
  function buildSparkline(values, opts) {
    opts = opts || {};
    const w = opts.w || 240, h = opts.h || 48;
    const d = sparklinePath(values, w, h, opts.pad);
    const pts = sparklinePoints(values, w, h, opts.pad);
    const last = pts.length ? pts[pts.length - 1] : null;
    const dot = last ? `<circle class="dot" cx="${fmtNum(last[0], 2)}" cy="${fmtNum(last[1], 2)}" r="2.2"/>` : "";
    return `<svg class="sparkline" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" `
      + `role="img" aria-label="${(opts.label || "trend").replace(/"/g, "")}">`
      + `<path d="${d}"/>${dot}</svg>`;
  }

  // Snow-vs-rain regime label from the annual snowmelt fraction — mirrors
  // src.flow_metrics.classify_regime (#69). Thresholds validate 0<=rainMax<snowMin<=1.
  const REGIME_SNOW_MIN = 0.4, REGIME_RAIN_MAX = 0.2;
  function classifyRegime(fraction, snowMin, rainMax) {
    snowMin = snowMin == null ? REGIME_SNOW_MIN : snowMin;
    rainMax = rainMax == null ? REGIME_RAIN_MAX : rainMax;
    if (!(rainMax >= 0 && rainMax < snowMin && snowMin <= 1)) {
      throw new Error("bad regime thresholds: need 0<=rainMax<snowMin<=1");
    }
    if (fraction >= snowMin) return "snowmelt";
    if (fraction <= rainMax) return "rain";
    return "transitional";
  }

  // Flow-weighted center-of-timing as a 0-based month index (Σ i·v / Σ v). NaN for
  // an empty or all-zero vector (no mass to weight). The Python center_of_timing is
  // 1-based; here 0-based to index MONTH_ABBR directly (matches the doc's monthIndex).
  function centerOfTimingIndex(v) {
    let num = 0, den = 0;
    (v || []).forEach((x, i) => { if (isFinite(x)) { num += i * x; den += x; } });
    return den > 0 ? num / den : NaN;
  }

  // Pearson correlation of two equal-length vectors; NaN when either is constant.
  function _pearson(a, b) {
    const n = Math.min(a.length, b.length);
    let sa = 0, sb = 0;
    for (let i = 0; i < n; i++) { sa += a[i]; sb += b[i]; }
    const ma = sa / n, mb = sb / n;
    let num = 0, da = 0, db = 0;
    for (let i = 0; i < n; i++) {
      const x = a[i] - ma, y = b[i] - mb;
      num += x * y; da += x * x; db += y * y;
    }
    return (da > 0 && db > 0) ? num / Math.sqrt(da * db) : NaN;
  }

  // A deterministic sample report document (delivery.py-style export) so the page
  // renders standalone over file:// with no build. Mirrors the ux.md mock (Salmon
  // Creek); real reports come from tools/build_watershed_report.py (#54).
  function sampleReport() {
    const rnd = mulberry32(0x5A1303);
    const years = [], peak = [], summerLow = [];
    for (let y = 1990; y <= 2023; y++) {
      years.push(y);
      peak.push(Math.round(470 + (y - 1990) * 3 + (rnd() - 0.5) * 240));
      summerLow.push(Number((0.9 - (y - 1990) * 0.01 + (rnd() - 0.5) * 0.3).toFixed(2)));
    }
    const mean = MONTH_ABBR.map((_, i) => Number((6 + 5 * Math.cos((i - 0) / 12 * 2 * Math.PI)).toFixed(2)));
    const lo = mean.map((v) => Number((v * 0.6).toFixed(2)));
    const hi = mean.map((v) => Number((v * 1.5).toFixed(2)));
    const enso = years.map((y, i) => {
      const oni = Number((Math.sin(i * 1.3) * 1.4).toFixed(2));
      return { year: y, oni, peak: peak[i], phase: oni >= 0 ? "wet" : "dry" };
    });

    // --- #76 derived sections (from synthetic per-year hydrographs) ----------
    // A 12-month hydrograph per year: the seasonal shape, scaled to the year's
    // peak and given a small deterministic phase jitter so analog shapes vary.
    const perYear = years.map((y, i) => {
      const shift = (rnd() - 0.5) * 2.2;
      const scale = peak[i] / peak[0];
      return MONTH_ABBR.map((_, m) =>
        Number(Math.max(0, scale * (6 + 5 * Math.cos((m - shift) / 12 * 2 * Math.PI))).toFixed(2)));
    });

    // Analog years (#71): most similar monthly *shape* to the latest year.
    const target = perYear[perYear.length - 1];
    const analogs = years.slice(0, -1)
      .map((y, i) => ({ year: y, similarity: Number(_pearson(perYear[i], target).toFixed(3)) }))
      .filter((a) => isFinite(a.similarity))
      .sort((a, b) => b.similarity - a.similarity || a.year - b.year)
      .slice(0, 6);

    // Drought/flood record book (#72): rank by summer-low (asc) and peak (desc).
    const rankBy = (vals, ascending) =>
      years.map((y, i) => ({ year: y, value: vals[i] }))
        .sort((a, b) => (ascending ? a.value - b.value : b.value - a.value) || a.year - b.year)
        .slice(0, 5)
        .map((r, i) => ({ year: r.year, value: r.value, rank: i + 1 }));
    const recordBook = { driest: rankBy(summerLow, true), wettest: rankBy(peak, false) };

    // Decade flow-duration curves (#73): pool each decade's monthly flows, take
    // exceedance quantiles (non-increasing in q by construction).
    const fdcQuantiles = [0, 10, 25, 50, 75, 90, 100];
    const byDecade = {};
    years.forEach((y, i) => {
      const d = Math.floor(y / 10) * 10;
      (byDecade[d] = byDecade[d] || []).push(...perYear[i]);
    });
    const exceedance = (sorted, q) => {
      if (!sorted.length) return NaN;
      const pos = (1 - q / 100) * (sorted.length - 1);
      const lo = Math.floor(pos), hi = Math.ceil(pos);
      return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
    };
    const fdc = Object.keys(byDecade).sort((a, b) => a - b).map((d) => {
      const sorted = byDecade[d].slice().sort((a, b) => a - b);
      return { decade: Number(d), flows: fdcQuantiles.map((q) => Number(exceedance(sorted, q).toFixed(2))) };
    });

    // ENSO/PDO composite hydrographs (#74): mean hydrograph per phase (ONI ±0.5).
    const phaseMean = (pred) => {
      const rows = perYear.filter((_, i) => pred(enso[i].oni));
      if (!rows.length) return new Array(12).fill(0);
      return MONTH_ABBR.map((_, m) =>
        Number((rows.reduce((s, v) => s + v[m], 0) / rows.length).toFixed(2)));
    };
    const composites = {
      warm: phaseMean((o) => o >= 0.5),
      neutral: phaseMean((o) => o > -0.5 && o < 0.5),
      cool: phaseMean((o) => o <= -0.5),
    };

    // Snow-vs-rain regime (#69): a synthetic snowmelt fraction + melt-pulse center.
    const meltShape = MONTH_ABBR.map((_, m) => Math.max(0, Math.cos((m - 4) / 12 * 2 * Math.PI)));
    const regimeFraction = 0.52;
    const regime = {
      fraction: regimeFraction,
      label: classifyRegime(regimeFraction),
      meltCenterMonth: Number(centerOfTimingIndex(meltShape).toFixed(1)),
      driftDaysPerDecade: -2.4, // melt pulse arriving earlier
    };

    return {
      watershed: "Salmon Creek",
      place: "Clark County, WA",
      range: [1990, 2023],
      metrics: {
        peak: { value: peak[peak.length - 1], unit: "cfs", pct: 0.92, trendPerDecade: 30 },
        summerLow: { value: summerLow[summerLow.length - 1], unit: "cfs", pct: 0.04, trendPerDecade: -0.1 },
        centerOfTiming: { monthIndex: 2, trendPerDecade: -0.3 }, // Mar, shifting earlier
      },
      validation: { verdict: "moderate", r: 0.71, nse: 0.55, bias: -3.2 },
      longRecord: { years, peak, summerLow },
      typicalYear: { months: MONTH_ABBR.slice(), mean, lo, hi },
      enso,
      regime,
      analogs,
      recordBook,
      fdc,
      fdcQuantiles,
      composites,
    };
  }
  const REPORT_SAMPLE = sampleReport();

  // ---- Public surface -----------------------------------------------------
  const HydroUX = {
    STATES, COUNTIES, PALETTES, HYPSO, MONTH_ABBR, HUC_LEVELS,
    mulberry32, hash, generateNetwork, buildSvg, applyStyles,
    seasonalMultiplier, yearMaxFlow,
    cliMapping, yamlMapping, scopeToken, monthsToken, stateAbbr,
    mappingSelfCheck, renderRequest,
    RECIPE_KEYS, DEFAULT_RECIPE,
    toRecipe, sanitizeRecipe, encodeRecipe, decodeRecipe, applyRecipe,
    b64url, b64urlDecode,
    PRESETS, presetById, applyPreset,
    drawSwatches, fillCounties, buildTimeline, paintTimeline, seg, bindRange,
    ordinal, trendArrow, fmtNum, verdictClass, verdictLabel,
    classifyRegime, centerOfTimingIndex,
    sparklinePoints, sparklinePath, buildSparkline, sampleReport, REPORT_SAMPLE,
  };
  global.HydroUX = HydroUX;
  if (typeof module !== "undefined" && module.exports) module.exports = HydroUX;

})(typeof window !== "undefined" ? window : (typeof globalThis !== "undefined" ? globalThis : this));
