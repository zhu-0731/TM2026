/*
   Licensed to the Apache Software Foundation (ASF) under one or more
   contributor license agreements.  See the NOTICE file distributed with
   this work for additional information regarding copyright ownership.
   The ASF licenses this file to You under the Apache License, Version 2.0
   (the "License"); you may not use this file except in compliance with
   the License.  You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
*/
var showControllersOnly = false;
var seriesFilter = "";
var filtersOnlySampleSeries = true;

/*
 * Add header in statistics table to group metrics by category
 * format
 *
 */
function summaryTableHeader(header) {
    var newRow = header.insertRow(-1);
    newRow.className = "tablesorter-no-sort";
    var cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 1;
    cell.innerHTML = "Requests";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 3;
    cell.innerHTML = "Executions";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 7;
    cell.innerHTML = "Response Times (ms)";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 1;
    cell.innerHTML = "Throughput";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 2;
    cell.innerHTML = "Network (KB/sec)";
    newRow.appendChild(cell);
}

/*
 * Populates the table identified by id parameter with the specified data and
 * format
 *
 */
function createTable(table, info, formatter, defaultSorts, seriesIndex, headerCreator) {
    var tableRef = table[0];

    // Create header and populate it with data.titles array
    var header = tableRef.createTHead();

    // Call callback is available
    if(headerCreator) {
        headerCreator(header);
    }

    var newRow = header.insertRow(-1);
    for (var index = 0; index < info.titles.length; index++) {
        var cell = document.createElement('th');
        cell.innerHTML = info.titles[index];
        newRow.appendChild(cell);
    }

    var tBody;

    // Create overall body if defined
    if(info.overall){
        tBody = document.createElement('tbody');
        tBody.className = "tablesorter-no-sort";
        tableRef.appendChild(tBody);
        var newRow = tBody.insertRow(-1);
        var data = info.overall.data;
        for(var index=0;index < data.length; index++){
            var cell = newRow.insertCell(-1);
            cell.innerHTML = formatter ? formatter(index, data[index]): data[index];
        }
    }

    // Create regular body
    tBody = document.createElement('tbody');
    tableRef.appendChild(tBody);

    var regexp;
    if(seriesFilter) {
        regexp = new RegExp(seriesFilter, 'i');
    }
    // Populate body with data.items array
    for(var index=0; index < info.items.length; index++){
        var item = info.items[index];
        if((!regexp || filtersOnlySampleSeries && !info.supportsControllersDiscrimination || regexp.test(item.data[seriesIndex]))
                &&
                (!showControllersOnly || !info.supportsControllersDiscrimination || item.isController)){
            if(item.data.length > 0) {
                var newRow = tBody.insertRow(-1);
                for(var col=0; col < item.data.length; col++){
                    var cell = newRow.insertCell(-1);
                    cell.innerHTML = formatter ? formatter(col, item.data[col]) : item.data[col];
                }
            }
        }
    }

    // Add support of columns sort
    table.tablesorter({sortList : defaultSorts});
}

$(document).ready(function() {

    // Customize table sorter default options
    $.extend( $.tablesorter.defaults, {
        theme: 'blue',
        cssInfoBlock: "tablesorter-no-sort",
        widthFixed: true,
        widgets: ['zebra']
    });

    var data = {"OkPercent": 78.74550539352776, "KoPercent": 21.25449460647223};
    var dataset = [
        {
            "label" : "FAIL",
            "data" : data.KoPercent,
            "color" : "#FF6347"
        },
        {
            "label" : "PASS",
            "data" : data.OkPercent,
            "color" : "#9ACD32"
        }];
    $.plot($("#flot-requests-summary"), dataset, {
        series : {
            pie : {
                show : true,
                radius : 1,
                label : {
                    show : true,
                    radius : 3 / 4,
                    formatter : function(label, series) {
                        return '<div style="font-size:8pt;text-align:center;padding:2px;color:white;">'
                            + label
                            + '<br/>'
                            + Math.round10(series.percent, -2)
                            + '%</div>';
                    },
                    background : {
                        opacity : 0.5,
                        color : '#000'
                    }
                }
            }
        },
        legend : {
            show : true
        }
    });

    // Creates APDEX table
    createTable($("#apdexTable"), {"supportsControllersDiscrimination": true, "overall": {"data": [0.3384938074310827, 500, 1500, "Total"], "isController": false}, "titles": ["Apdex", "T (Toleration threshold)", "F (Frustration threshold)", "Label"], "items": [{"data": [0.0, 500, 1500, "4.1 Homepage / (Frontend+Recommendation+AdService)"], "isController": false}, {"data": [0.40625, 500, 1500, "3.2 Product Detail /product/6E92ZMYYFZ (ProductCatalogService)"], "isController": false}, {"data": [0.0, 500, 1500, "1.6 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)"], "isController": false}, {"data": [0.5416666666666666, 500, 1500, "1.4 Add to Cart /cart (CartService)-1"], "isController": false}, {"data": [0.23, 500, 1500, "3.1 Homepage / (Frontend+Recommendation+AdService)"], "isController": false}, {"data": [0.23875, 500, 1500, "3.3 Add to Cart /cart (CartService)"], "isController": false}, {"data": [0.0, 500, 1500, "1.5 View Cart /cart (CartService)"], "isController": false}, {"data": [0.31, 500, 1500, "2.4 Add to Cart /cart (CartService)"], "isController": false}, {"data": [0.12125, 500, 1500, "3.4 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)"], "isController": false}, {"data": [0.9583333333333334, 500, 1500, "1.4 Add to Cart /cart (CartService)-0"], "isController": false}, {"data": [0.025, 500, 1500, "4.2 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)"], "isController": false}, {"data": [0.3277777777777778, 500, 1500, "5.1 Add Item to Cart /cart (CartService)-1"], "isController": false}, {"data": [0.9222222222222223, 500, 1500, "5.1 Add Item to Cart /cart (CartService)-0"], "isController": false}, {"data": [0.10833333333333334, 500, 1500, "5.4 Checkout with FREESHIP (CouponService+Checkout)"], "isController": false}, {"data": [0.08055555555555556, 500, 1500, "5.3 Checkout with OFF15 ($15 off) (CouponService+Checkout)"], "isController": false}, {"data": [0.23333333333333334, 500, 1500, "1.1 Homepage / (Frontend+Recommendation+AdService)"], "isController": false}, {"data": [0.37, 500, 1500, "2.4 Add to Cart /cart (CartService)-1"], "isController": false}, {"data": [0.375, 500, 1500, "1.4 Add to Cart /cart (CartService)"], "isController": false}, {"data": [0.99, 500, 1500, "2.4 Add to Cart /cart (CartService)-0"], "isController": false}, {"data": [0.455, 500, 1500, "2.3 Product Detail /product/1YMWWN1N4O (ProductCatalogService)"], "isController": false}, {"data": [0.255, 500, 1500, "2.2 Set Currency /setCurrency (CurrencyService)-1"], "isController": false}, {"data": [0.255, 500, 1500, "2.1 Homepage / (Frontend+Recommendation+AdService)"], "isController": false}, {"data": [0.99, 500, 1500, "2.2 Set Currency /setCurrency (CurrencyService)-0"], "isController": false}, {"data": [0.96125, 500, 1500, "3.3 Add to Cart /cart (CartService)-0"], "isController": false}, {"data": [0.19230769230769232, 500, 1500, "1.2 Set Currency /setCurrency (CurrencyService)-1"], "isController": false}, {"data": [0.32875, 500, 1500, "3.3 Add to Cart /cart (CartService)-1"], "isController": false}, {"data": [1.0, 500, 1500, "1.2 Set Currency /setCurrency (CurrencyService)-0"], "isController": false}, {"data": [0.6666666666666666, 500, 1500, "1.3 Product Detail /product/OLJCESPC7Z (ProductCatalogService)"], "isController": false}, {"data": [0.37, 500, 1500, "2.5 View Cart /cart (CartService)"], "isController": false}, {"data": [0.0, 500, 1500, "2.6 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)"], "isController": false}, {"data": [0.225, 500, 1500, "5.1 Add Item to Cart /cart (CartService)"], "isController": false}, {"data": [0.19230769230769232, 500, 1500, "1.2 Set Currency /setCurrency (CurrencyService)"], "isController": false}, {"data": [0.0, 500, 1500, "5.2 Checkout with SAVE10 (10% off) (CouponService+Checkout)"], "isController": false}, {"data": [0.24, 500, 1500, "2.2 Set Currency /setCurrency (CurrencyService)"], "isController": false}]}, function(index, item){
        switch(index){
            case 0:
                item = item.toFixed(3);
                break;
            case 1:
            case 2:
                item = formatDuration(item);
                break;
        }
        return item;
    }, [[0, 0]], 3);

    // Create statistics table
    createTable($("#statisticsTable"), {"supportsControllersDiscrimination": true, "overall": {"data": ["Total", 5006, 1064, 21.25449460647223, 2093.5063923292073, 3, 22205, 1115.5, 4309.900000000001, 6447.899999999998, 20959.58, 40.69654006243496, 364.684320265247, 26.233041943918284], "isController": false}, "titles": ["Label", "#Samples", "FAIL", "Error %", "Average", "Min", "Max", "Median", "90th pct", "95th pct", "99th pct", "Transactions/s", "Received", "Sent"], "items": [{"data": ["4.1 Homepage / (Frontend+Recommendation+AdService)", 200, 0, 0.0, 4677.780000000001, 2233, 6517, 4725.0, 5736.3, 6065.349999999999, 6515.7300000000005, 12.103606874848705, 127.0878721859114, 4.9880098644396025], "isController": false}, {"data": ["3.2 Product Detail /product/6E92ZMYYFZ (ProductCatalogService)", 400, 45, 11.25, 1425.1425000000008, 4, 21070, 1073.5, 1939.3000000000002, 2441.0499999999997, 20686.02, 3.4229284864665965, 26.228039105888293, 1.5744133956306319], "isController": false}, {"data": ["1.6 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)", 12, 12, 100.0, 8503.41666666667, 193, 19937, 4999.5, 19207.700000000004, 19937.0, 19937.0, 0.28891296496930297, 1.7952197694715302, 0.23192036836403035], "isController": false}, {"data": ["1.4 Add to Cart /cart (CartService)-1", 12, 0, 0.0, 1058.1666666666665, 76, 1885, 1153.0, 1759.3000000000004, 1885.0, 1885.0, 0.2872531418312388, 4.862638390185518, 0.1335278276481149], "isController": false}, {"data": ["3.1 Homepage / (Frontend+Recommendation+AdService)", 400, 40, 10.0, 2224.2649999999994, 4, 21766, 1604.0, 3968.5000000000005, 4545.749999999999, 21141.59, 3.294865775405474, 33.00720275677301, 1.4326552602532105], "isController": false}, {"data": ["3.3 Add to Cart /cart (CartService)", 400, 64, 16.0, 2260.2724999999987, 10, 22205, 1480.5, 2669.9000000000024, 3823.449999999998, 21721.24, 3.4633533919217285, 52.7314916906576, 3.487028659249318], "isController": false}, {"data": ["1.5 View Cart /cart (CartService)", 12, 12, 100.0, 976.9166666666667, 224, 1666, 844.0, 1658.5, 1666.0, 1666.0, 0.28557149996430353, 4.835286969610433, 0.13274612693653173], "isController": false}, {"data": ["2.4 Add to Cart /cart (CartService)", 100, 15, 15.0, 2011.94, 13, 21874, 1231.5, 2719.800000000001, 3178.9499999999985, 21873.84, 0.9672208842333324, 14.837300601369586, 1.0097257082474924], "isController": false}, {"data": ["3.4 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)", 400, 221, 55.25, 2291.12, 7, 21262, 972.0, 5678.000000000001, 15328.949999999997, 20723.42000000001, 3.534942910671993, 21.128472874284174, 2.7927429831383224], "isController": false}, {"data": ["1.4 Add to Cart /cart (CartService)-0", 12, 0, 0.0, 191.58333333333334, 14, 865, 102.5, 747.7000000000005, 865.0, 865.0, 0.29145313676438445, 0.048955019065892696, 0.1687809668957812], "isController": false}, {"data": ["4.2 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)", 200, 0, 0.0, 6480.499999999999, 826, 21406, 3795.5, 20213.1, 20739.0, 21366.83, 5.955216769890424, 40.87982977385064, 4.699038232491662], "isController": false}, {"data": ["5.1 Add Item to Cart /cart (CartService)-1", 180, 0, 0.0, 1373.7722222222224, 18, 3169, 1395.0, 2194.0, 2478.9, 3139.84, 1.9844113464230988, 33.5901347367072, 0.8856210794095274], "isController": false}, {"data": ["5.1 Add Item to Cart /cart (CartService)-0", 180, 0, 0.0, 286.26666666666665, 8, 2277, 203.5, 652.9, 878.95, 2171.7, 1.995963717815085, 0.36189836940852943, 1.0986896636801136], "isController": false}, {"data": ["5.4 Checkout with FREESHIP (CouponService+Checkout)", 180, 107, 59.44444444444444, 1736.8222222222219, 19, 21356, 1000.0, 2504.5000000000005, 4674.549999999992, 20610.8, 1.6805310478111082, 10.35646404888945, 1.3572257583396354], "isController": false}, {"data": ["5.3 Checkout with OFF15 ($15 off) (CouponService+Checkout)", 180, 108, 60.0, 1745.5277777777799, 14, 16748, 906.0, 3689.0000000000005, 6387.549999999991, 16725.32, 1.6617583249476084, 10.22240118019461, 1.3371961521062787], "isController": false}, {"data": ["1.1 Homepage / (Frontend+Recommendation+AdService)", 15, 8, 53.333333333333336, 2656.2, 434, 4963, 3368.0, 4959.4, 4963.0, 4963.0, 0.25612567232988986, 2.6935216212755058, 0.11130461346367285], "isController": false}, {"data": ["2.4 Add to Cart /cart (CartService)-1", 100, 15, 15.0, 1865.7000000000007, 5, 21770, 1076.5, 2331.4, 2953.999999999997, 21769.88, 0.9679323996012118, 14.685632949144832, 0.4499373263771258], "isController": false}, {"data": ["1.4 Add to Cart /cart (CartService)", 12, 0, 0.0, 1249.9166666666667, 90, 1946, 1349.5, 1944.5, 1946.0, 1946.0, 0.28142589118198874, 4.811265097326454, 0.2937932399155722], "isController": false}, {"data": ["2.4 Add to Cart /cart (CartService)-0", 100, 0, 0.0, 146.01999999999998, 7, 705, 114.0, 343.9000000000001, 407.1999999999996, 703.059999999999, 0.9672770184653182, 0.16247231169534643, 0.5601516327636072], "isController": false}, {"data": ["2.3 Product Detail /product/1YMWWN1N4O (ProductCatalogService)", 100, 11, 11.0, 1657.4599999999996, 6, 20916, 848.0, 1923.8000000000006, 3186.34999999999, 20913.079999999998, 0.9378135814162861, 7.243932199594864, 0.4487584520449025], "isController": false}, {"data": ["2.2 Set Currency /setCurrency (CurrencyService)-1", 100, 7, 7.0, 3026.9300000000003, 4, 21087, 1791.5, 4671.4, 20083.049999999992, 21084.42, 0.901445016361227, 9.143997672018244, 0.4155098122290031], "isController": false}, {"data": ["2.1 Homepage / (Frontend+Recommendation+AdService)", 100, 31, 31.0, 2289.1800000000007, 44, 21731, 1819.5, 4220.500000000001, 4872.899999999995, 21566.259999999915, 0.8724176437744277, 9.136819759605318, 0.38832808792225015], "isController": false}, {"data": ["2.2 Set Currency /setCurrency (CurrencyService)-0", 100, 0, 0.0, 81.32999999999997, 4, 596, 54.0, 186.2000000000001, 248.64999999999992, 595.2699999999996, 0.9006088115566123, 0.18909267039518715, 0.5111658606217803], "isController": false}, {"data": ["3.3 Add to Cart /cart (CartService)-0", 400, 0, 0.0, 197.295, 6, 1942, 141.0, 443.50000000000017, 586.8499999999997, 1331.2800000000025, 3.4635033336219587, 0.5817603255693133, 1.9414559702138714], "isController": false}, {"data": ["1.2 Set Currency /setCurrency (CurrencyService)-1", 13, 0, 0.0, 2235.769230769231, 501, 4962, 1705.0, 4719.599999999999, 4962.0, 4962.0, 0.23210555446446107, 2.4336734665410917, 0.10698615401096252], "isController": false}, {"data": ["3.3 Add to Cart /cart (CartService)-1", 400, 64, 16.0, 2062.7800000000007, 3, 21969, 1294.0, 2209.5000000000005, 2994.549999999999, 21592.81, 3.4698427293782905, 52.24747033555548, 1.5485528587166788], "isController": false}, {"data": ["1.2 Set Currency /setCurrency (CurrencyService)-0", 13, 0, 0.0, 99.9230769230769, 10, 331, 71.0, 307.79999999999995, 331.0, 331.0, 0.24174802417480243, 0.05075764179451418, 0.13638278707577872], "isController": false}, {"data": ["1.3 Product Detail /product/OLJCESPC7Z (ProductCatalogService)", 12, 0, 0.0, 648.75, 30, 1398, 644.0, 1272.0000000000005, 1398.0, 1398.0, 0.2818952759050013, 2.2603926859921537, 0.13489129413422912], "isController": false}, {"data": ["2.5 View Cart /cart (CartService)", 100, 17, 17.0, 1380.6799999999998, 4, 21349, 1128.0, 2061.4, 2239.3499999999995, 21345.379999999997, 0.9907169818797864, 14.808151913446011, 0.460528597045682], "isController": false}, {"data": ["2.6 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)", 100, 100, 100.0, 3783.719999999998, 7, 20859, 1039.0, 14421.3, 16110.649999999998, 20822.839999999982, 0.9920339672430385, 5.884524611122685, 0.800214899358154], "isController": false}, {"data": ["5.1 Add Item to Cart /cart (CartService)", 180, 0, 0.0, 1660.3222222222219, 29, 4160, 1625.0, 2673.9, 3160.85, 3955.879999999999, 1.9827063942281213, 33.92076962397422, 1.9762522718510769], "isController": false}, {"data": ["1.2 Set Currency /setCurrency (CurrencyService)", 13, 0, 0.0, 2336.153846153846, 513, 5054, 1885.0, 4783.599999999999, 5054.0, 5054.0, 0.23201442058860275, 2.4814318747657547, 0.23783569586478914], "isController": false}, {"data": ["5.2 Checkout with SAVE10 (10% off) (CouponService+Checkout)", 180, 180, 100.0, 3623.966666666669, 119, 21169, 1165.0, 14295.600000000002, 16585.649999999998, 20655.46, 1.6374354122698493, 10.014127499931774, 1.3192228663306893], "isController": false}, {"data": ["2.2 Set Currency /setCurrency (CurrencyService)", 100, 7, 7.0, 3108.6699999999996, 41, 21173, 1877.5, 4763.2, 20092.84999999999, 21170.019999999997, 0.9005763688760806, 9.324272221721902, 0.9262568668948127], "isController": false}]}, function(index, item){
        switch(index){
            // Errors pct
            case 3:
                item = item.toFixed(2) + '%';
                break;
            // Mean
            case 4:
            // Mean
            case 7:
            // Median
            case 8:
            // Percentile 1
            case 9:
            // Percentile 2
            case 10:
            // Percentile 3
            case 11:
            // Throughput
            case 12:
            // Kbytes/s
            case 13:
            // Sent Kbytes/s
                item = item.toFixed(2);
                break;
        }
        return item;
    }, [[0, 0]], 0, summaryTableHeader);

    // Create error table
    createTable($("#errorsTable"), {"supportsControllersDiscrimination": false, "titles": ["Type of error", "Number of errors", "% in errors", "% in all samples"], "items": [{"data": ["The operation lasted too long: It took 4,472 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,809 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 4,963 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 5,221 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,444 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,251 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,749 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 4,267 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,972 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 5,625 milliseconds, but should not have lasted longer than 5,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,627 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 4,063 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,988 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 5,070 milliseconds, but should not have lasted longer than 5,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,200 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,613 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,082 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,750 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 4,238 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 4,957 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,995 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 4,894 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,952 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,390 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 5,646 milliseconds, but should not have lasted longer than 5,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,092 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 4,374 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["Test failed: text expected to contain /Shopping Cart/", 12, 1.1278195488721805, 0.23971234518577705], "isController": false}, {"data": ["The operation lasted too long: It took 4,381 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,844 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,698 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 4,009 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,942 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,704 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,393 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,778 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 5,257 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["Test failed: text expected to contain /Order Confirmation/", 118, 11.090225563909774, 2.357171394326808], "isController": false}, {"data": ["500/Internal Server Error", 893, 83.92857142857143, 17.83859368757491], "isController": false}, {"data": ["The operation lasted too long: It took 3,324 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,368 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,640 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 3,852 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}, {"data": ["The operation lasted too long: It took 5,185 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.09398496240601503, 0.01997602876548142], "isController": false}]}, function(index, item){
        switch(index){
            case 2:
            case 3:
                item = item.toFixed(2) + '%';
                break;
        }
        return item;
    }, [[1, 1]]);

        // Create top5 errors by sampler
    createTable($("#top5ErrorsBySamplerTable"), {"supportsControllersDiscrimination": false, "overall": {"data": ["Total", 5006, 1064, "500/Internal Server Error", 893, "Test failed: text expected to contain /Order Confirmation/", 118, "Test failed: text expected to contain /Shopping Cart/", 12, "The operation lasted too long: It took 4,472 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 3,809 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1], "isController": false}, "titles": ["Sample", "#Samples", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors"], "items": [{"data": [], "isController": false}, {"data": ["3.2 Product Detail /product/6E92ZMYYFZ (ProductCatalogService)", 400, 45, "500/Internal Server Error", 45, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["1.6 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)", 12, 12, "Test failed: text expected to contain /Order Confirmation/", 7, "500/Internal Server Error", 5, "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": ["3.1 Homepage / (Frontend+Recommendation+AdService)", 400, 40, "500/Internal Server Error", 37, "The operation lasted too long: It took 5,070 milliseconds, but should not have lasted longer than 5,000 milliseconds.", 1, "The operation lasted too long: It took 5,646 milliseconds, but should not have lasted longer than 5,000 milliseconds.", 1, "The operation lasted too long: It took 5,625 milliseconds, but should not have lasted longer than 5,000 milliseconds.", 1, "", ""], "isController": false}, {"data": ["3.3 Add to Cart /cart (CartService)", 400, 64, "500/Internal Server Error", 64, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["1.5 View Cart /cart (CartService)", 12, 12, "Test failed: text expected to contain /Shopping Cart/", 12, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["2.4 Add to Cart /cart (CartService)", 100, 15, "500/Internal Server Error", 15, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["3.4 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)", 400, 221, "500/Internal Server Error", 221, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["5.4 Checkout with FREESHIP (CouponService+Checkout)", 180, 107, "500/Internal Server Error", 107, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["5.3 Checkout with OFF15 ($15 off) (CouponService+Checkout)", 180, 108, "500/Internal Server Error", 108, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["1.1 Homepage / (Frontend+Recommendation+AdService)", 15, 8, "The operation lasted too long: It took 3,809 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 4,963 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 3,952 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 3,750 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 3,972 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1], "isController": false}, {"data": ["2.4 Add to Cart /cart (CartService)-1", 100, 15, "500/Internal Server Error", 15, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["2.3 Product Detail /product/1YMWWN1N4O (ProductCatalogService)", 100, 11, "500/Internal Server Error", 11, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["2.2 Set Currency /setCurrency (CurrencyService)-1", 100, 7, "500/Internal Server Error", 7, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["2.1 Homepage / (Frontend+Recommendation+AdService)", 100, 31, "The operation lasted too long: It took 4,472 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 5,221 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 3,444 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 3,251 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 3,749 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["3.3 Add to Cart /cart (CartService)-1", 400, 64, "500/Internal Server Error", 64, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["2.5 View Cart /cart (CartService)", 100, 17, "500/Internal Server Error", 17, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["2.6 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)", 100, 100, "500/Internal Server Error", 58, "Test failed: text expected to contain /Order Confirmation/", 42, "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["5.2 Checkout with SAVE10 (10% off) (CouponService+Checkout)", 180, 180, "500/Internal Server Error", 111, "Test failed: text expected to contain /Order Confirmation/", 69, "", "", "", "", "", ""], "isController": false}, {"data": ["2.2 Set Currency /setCurrency (CurrencyService)", 100, 7, "500/Internal Server Error", 7, "", "", "", "", "", "", "", ""], "isController": false}]}, function(index, item){
        return item;
    }, [[0, 0]], 0);

});
