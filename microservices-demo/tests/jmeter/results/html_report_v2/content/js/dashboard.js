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

    var data = {"OkPercent": 93.6229573535273, "KoPercent": 6.377042646472698};
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
    createTable($("#apdexTable"), {"supportsControllersDiscrimination": true, "overall": {"data": [0.3447588680749302, 500, 1500, "Total"], "isController": false}, "titles": ["Apdex", "T (Toleration threshold)", "F (Frustration threshold)", "Label"], "items": [{"data": [0.005, 500, 1500, "4.1 Homepage / (Frontend+Recommendation+AdService)"], "isController": false}, {"data": [0.33, 500, 1500, "3.2 Product Detail /product/6E92ZMYYFZ (ProductCatalogService)"], "isController": false}, {"data": [0.0, 500, 1500, "1.6 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)"], "isController": false}, {"data": [0.34615384615384615, 500, 1500, "1.4 Add to Cart /cart (CartService)-1"], "isController": false}, {"data": [0.295, 500, 1500, "3.1 Homepage / (Frontend+Recommendation+AdService)"], "isController": false}, {"data": [0.225, 500, 1500, "3.3 Add to Cart /cart (CartService)"], "isController": false}, {"data": [0.0, 500, 1500, "1.5 View Cart /cart (CartService)"], "isController": false}, {"data": [0.22, 500, 1500, "2.4 Add to Cart /cart (CartService)"], "isController": false}, {"data": [0.3475, 500, 1500, "3.4 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)"], "isController": false}, {"data": [0.9230769230769231, 500, 1500, "1.4 Add to Cart /cart (CartService)-0"], "isController": false}, {"data": [0.0675, 500, 1500, "4.2 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)"], "isController": false}, {"data": [0.15, 500, 1500, "5.1 Add Item to Cart /cart (CartService)-1"], "isController": false}, {"data": [0.9277777777777778, 500, 1500, "5.1 Add Item to Cart /cart (CartService)-0"], "isController": false}, {"data": [0.24722222222222223, 500, 1500, "5.4 Checkout with FREESHIP (CouponService+Checkout)"], "isController": false}, {"data": [0.30277777777777776, 500, 1500, "5.3 Checkout with OFF15 ($15 off) (CouponService+Checkout)"], "isController": false}, {"data": [0.13333333333333333, 500, 1500, "1.1 Homepage / (Frontend+Recommendation+AdService)"], "isController": false}, {"data": [0.285, 500, 1500, "2.4 Add to Cart /cart (CartService)-1"], "isController": false}, {"data": [0.965, 500, 1500, "2.4 Add to Cart /cart (CartService)-0"], "isController": false}, {"data": [0.2692307692307692, 500, 1500, "1.4 Add to Cart /cart (CartService)"], "isController": false}, {"data": [0.34, 500, 1500, "2.3 Product Detail /product/1YMWWN1N4O (ProductCatalogService)"], "isController": false}, {"data": [0.28, 500, 1500, "2.2 Set Currency /setCurrency (CurrencyService)-1"], "isController": false}, {"data": [0.24, 500, 1500, "2.1 Homepage / (Frontend+Recommendation+AdService)"], "isController": false}, {"data": [0.965, 500, 1500, "2.2 Set Currency /setCurrency (CurrencyService)-0"], "isController": false}, {"data": [0.96375, 500, 1500, "3.3 Add to Cart /cart (CartService)-0"], "isController": false}, {"data": [0.16666666666666666, 500, 1500, "1.2 Set Currency /setCurrency (CurrencyService)-1"], "isController": false}, {"data": [0.28625, 500, 1500, "3.3 Add to Cart /cart (CartService)-1"], "isController": false}, {"data": [0.9666666666666667, 500, 1500, "1.2 Set Currency /setCurrency (CurrencyService)-0"], "isController": false}, {"data": [0.36666666666666664, 500, 1500, "1.3 Product Detail /product/OLJCESPC7Z (ProductCatalogService)"], "isController": false}, {"data": [0.275, 500, 1500, "2.5 View Cart /cart (CartService)"], "isController": false}, {"data": [0.0, 500, 1500, "2.6 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)"], "isController": false}, {"data": [0.08055555555555556, 500, 1500, "5.1 Add Item to Cart /cart (CartService)"], "isController": false}, {"data": [0.16666666666666666, 500, 1500, "1.2 Set Currency /setCurrency (CurrencyService)"], "isController": false}, {"data": [0.0, 500, 1500, "5.2 Checkout with SAVE10 (10% off) (CouponService+Checkout)"], "isController": false}, {"data": [0.25, 500, 1500, "2.2 Set Currency /setCurrency (CurrencyService)"], "isController": false}]}, function(index, item){
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
    createTable($("#statisticsTable"), {"supportsControllersDiscrimination": true, "overall": {"data": ["Total", 5018, 320, 6.377042646472698, 1704.3611000398569, 9, 10668, 1452.5, 2872.600000000002, 5031.05, 8517.62, 46.00124674562722, 444.9190782733948, 29.65170297374042], "isController": false}, "titles": ["Label", "#Samples", "FAIL", "Error %", "Average", "Min", "Max", "Median", "90th pct", "95th pct", "99th pct", "Transactions/s", "Received", "Sent"], "items": [{"data": ["4.1 Homepage / (Frontend+Recommendation+AdService)", 200, 0, 0.0, 4420.794999999998, 1326, 8386, 4567.0, 5976.2, 6472.749999999999, 6927.5, 10.017028949213664, 105.17880396674346, 4.12811153961735], "isController": false}, {"data": ["3.2 Product Detail /product/6E92ZMYYFZ (ProductCatalogService)", 400, 0, 0.0, 1763.1575000000012, 22, 9072, 1432.0, 2490.4000000000005, 7635.049999999992, 8644.2, 3.7843309775873, 30.018595699817407, 1.740644424261346], "isController": false}, {"data": ["1.6 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)", 12, 12, 100.0, 3452.6666666666665, 1368, 8399, 1837.5, 8395.7, 8399.0, 8399.0, 0.306787677361626, 2.1071679662533556, 0.24626901444458646], "isController": false}, {"data": ["1.4 Add to Cart /cart (CartService)-1", 13, 0, 0.0, 2183.769230769231, 189, 8306, 1406.0, 6587.199999999999, 8306.0, 8306.0, 0.29706816571833367, 5.0285124740065354, 0.13809028015813166], "isController": false}, {"data": ["3.1 Homepage / (Frontend+Recommendation+AdService)", 400, 3, 0.75, 1559.3025, 33, 6111, 1431.0, 2533.6000000000004, 2812.6, 4866.670000000001, 3.710988236167291, 38.85393811231306, 1.6135913204623893], "isController": false}, {"data": ["3.3 Add to Cart /cart (CartService)", 400, 0, 0.0, 1801.0399999999986, 36, 8516, 1833.0, 2627.2000000000003, 2815.6, 8247.100000000028, 3.814646334601703, 65.1732140004673, 3.8407230185296446], "isController": false}, {"data": ["1.5 View Cart /cart (CartService)", 12, 12, 100.0, 1730.7500000000002, 503, 8514, 1069.5, 6645.000000000006, 8514.0, 8514.0, 0.31511777526850665, 5.335101904493054, 0.14648052834746986], "isController": false}, {"data": ["2.4 Add to Cart /cart (CartService)", 100, 0, 0.0, 1957.1499999999996, 258, 8726, 1791.5, 2641.5, 4813.949999999976, 8725.4, 1.063399902167209, 18.182185991301388, 1.1101313431804165], "isController": false}, {"data": ["3.4 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)", 400, 0, 0.0, 1568.6850000000006, 32, 9273, 1383.5, 2312.0, 2995.1499999999983, 8521.92, 3.978516013526954, 27.312862107121543, 3.143183061468072], "isController": false}, {"data": ["1.4 Add to Cart /cart (CartService)-0", 13, 0, 0.0, 263.8461538461538, 10, 1340, 142.0, 1126.3999999999999, 1340.0, 1340.0, 0.30069622741886987, 0.050507569449263295, 0.1741336551361229], "isController": false}, {"data": ["4.2 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)", 200, 0, 0.0, 3003.47, 856, 9553, 2240.0, 5626.0, 6755.949999999996, 8466.45, 8.26856292376385, 56.743255307383826, 6.524412932032413], "isController": false}, {"data": ["5.1 Add Item to Cart /cart (CartService)-1", 180, 0, 0.0, 2011.4444444444443, 503, 8993, 1777.5, 2514.2000000000003, 3623.6499999999915, 8991.38, 1.9564792069737615, 33.11145749548923, 0.8731552710810635], "isController": false}, {"data": ["5.1 Add Item to Cart /cart (CartService)-0", 180, 0, 0.0, 315.0666666666665, 11, 3347, 196.5, 669.7, 1134.0499999999995, 3146.1199999999994, 1.9735110955179371, 0.3578273698579072, 1.0863304891018333], "isController": false}, {"data": ["5.4 Checkout with FREESHIP (CouponService+Checkout)", 180, 0, 0.0, 2047.716666666669, 510, 9163, 1509.0, 2616.7000000000016, 8452.95, 9054.46, 2.031809100247204, 15.1129691150907, 1.640923951078552], "isController": false}, {"data": ["5.3 Checkout with OFF15 ($15 off) (CouponService+Checkout)", 180, 0, 0.0, 1857.033333333333, 423, 8699, 1372.5, 2440.4, 6695.4, 8685.23, 1.9729486814126311, 14.669845363296579, 1.5876071420742268], "isController": false}, {"data": ["1.1 Homepage / (Frontend+Recommendation+AdService)", 15, 4, 26.666666666666668, 2420.066666666667, 412, 5458, 2156.0, 4925.8, 5458.0, 5458.0, 0.2803161966698436, 2.9430463187475473, 0.12181709718562538], "isController": false}, {"data": ["2.4 Add to Cart /cart (CartService)-1", 100, 0, 0.0, 1727.7199999999996, 171, 8598, 1492.0, 2381.0, 4113.399999999982, 8597.98, 1.0666439115965525, 18.05848975221862, 0.49582275578121005], "isController": false}, {"data": ["2.4 Add to Cart /cart (CartService)-0", 100, 0, 0.0, 229.23, 16, 1411, 183.0, 424.70000000000016, 668.0999999999993, 1405.119999999997, 1.0679881239720614, 0.17938863019843218, 0.6184735913236645], "isController": false}, {"data": ["1.4 Add to Cart /cart (CartService)", 13, 0, 0.0, 2447.769230769231, 201, 8466, 1531.0, 7173.5999999999985, 8466.0, 8466.0, 0.28824194585485907, 4.927525512183766, 0.30090882824105897], "isController": false}, {"data": ["2.3 Product Detail /product/1YMWWN1N4O (ProductCatalogService)", 100, 0, 0.0, 1737.42, 152, 8831, 1403.0, 2432.900000000002, 7340.299999999978, 8830.24, 1.053230257198829, 8.398667894118763, 0.5039871347924083], "isController": false}, {"data": ["2.2 Set Currency /setCurrency (CurrencyService)-1", 100, 0, 0.0, 1620.95, 63, 5506, 1494.0, 2531.2000000000007, 3219.5499999999975, 5499.3799999999965, 1.0185166323766066, 10.672542446680653, 0.46947251023609216], "isController": false}, {"data": ["2.1 Homepage / (Frontend+Recommendation+AdService)", 100, 9, 9.0, 1782.4, 236, 6253, 1535.5, 2799.800000000001, 4171.95, 6250.809999999999, 1.0001900361068603, 10.492813947149958, 0.4452017758374091], "isController": false}, {"data": ["2.2 Set Currency /setCurrency (CurrencyService)-0", 100, 0, 0.0, 176.66999999999993, 10, 3343, 66.0, 208.70000000000002, 483.9999999999991, 3338.419999999998, 1.0232900822725226, 0.21485094500839097, 0.5807970662273341], "isController": false}, {"data": ["3.3 Add to Cart /cart (CartService)-0", 400, 0, 0.0, 214.5600000000001, 9, 1415, 158.0, 414.70000000000044, 685.2999999999998, 1123.1500000000008, 3.816502557056713, 0.6410531638806197, 2.1393285817876495], "isController": false}, {"data": ["1.2 Set Currency /setCurrency (CurrencyService)-1", 15, 0, 0.0, 2565.3999999999996, 654, 6359, 1694.0, 5463.200000000001, 6359.0, 6359.0, 0.28726827026198865, 3.010145058506971, 0.1324127183238854], "isController": false}, {"data": ["3.3 Add to Cart /cart (CartService)-1", 400, 0, 0.0, 1586.28, 26, 8233, 1574.5, 2386.8, 2533.0, 8092.610000000034, 3.8363048711481103, 64.89887065778242, 1.7121009044088735], "isController": false}, {"data": ["1.2 Set Currency /setCurrency (CurrencyService)-0", 15, 0, 0.0, 143.93333333333334, 10, 663, 77.0, 498.0000000000001, 663.0, 663.0, 0.2921243281140453, 0.06133469779738257, 0.1650806750019475], "isController": false}, {"data": ["1.3 Product Detail /product/OLJCESPC7Z (ProductCatalogService)", 15, 0, 0.0, 1460.1999999999998, 759, 3922, 1234.0, 2924.8000000000006, 3922.0, 3922.0, 0.31293680762731313, 2.500499557976759, 0.1497451520872885], "isController": false}, {"data": ["2.5 View Cart /cart (CartService)", 100, 0, 0.0, 1890.779999999999, 89, 8592, 1566.0, 2601.5, 8268.5, 8590.089999999998, 1.1386409182000363, 19.28023749914602, 0.5292901143195482], "isController": false}, {"data": ["2.6 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)", 100, 100, 100.0, 1696.189999999999, 66, 8747, 1519.0, 2281.4000000000005, 2596.2, 8745.179999999998, 1.1349578363163808, 7.797359839800702, 0.9155030984348932], "isController": false}, {"data": ["5.1 Add Item to Cart /cart (CartService)", 180, 0, 0.0, 2326.788888888889, 569, 9201, 2029.0, 3093.3000000000006, 4828.299999999996, 9055.199999999999, 1.9497611542586033, 33.351282306459126, 1.9434142755012511], "isController": false}, {"data": ["1.2 Set Currency /setCurrency (CurrencyService)", 15, 0, 0.0, 2709.7333333333336, 664, 7023, 1801.0, 5922.000000000001, 7023.0, 7023.0, 0.283661119515885, 3.0319052276380485, 0.29104812783661116], "isController": false}, {"data": ["5.2 Checkout with SAVE10 (10% off) (CouponService+Checkout)", 180, 180, 100.0, 2238.8111111111116, 719, 10668, 1699.5, 4513.400000000001, 8463.849999999999, 10662.33, 1.9390283313583971, 14.42146009506625, 1.5622054427448024], "isController": false}, {"data": ["2.2 Set Currency /setCurrency (CurrencyService)", 100, 0, 0.0, 1798.0400000000002, 76, 6301, 1537.5, 3014.3000000000006, 4520.5499999999965, 6292.329999999995, 1.017076718096846, 10.871000663642558, 1.0460792963863264], "isController": false}]}, function(index, item){
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
    createTable($("#errorsTable"), {"supportsControllersDiscrimination": false, "titles": ["Type of error", "Number of errors", "% in errors", "% in all samples"], "items": [{"data": ["The operation lasted too long: It took 4,115 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["The operation lasted too long: It took 5,054 milliseconds, but should not have lasted longer than 5,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["The operation lasted too long: It took 4,152 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["The operation lasted too long: It took 4,571 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["The operation lasted too long: It took 3,135 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["The operation lasted too long: It took 6,034 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["The operation lasted too long: It took 5,422 milliseconds, but should not have lasted longer than 5,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["Test failed: text expected to contain /Shopping Cart/", 12, 3.75, 0.2391390992427262], "isController": false}, {"data": ["The operation lasted too long: It took 4,173 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["The operation lasted too long: It took 6,111 milliseconds, but should not have lasted longer than 5,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["The operation lasted too long: It took 5,458 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["The operation lasted too long: It took 6,253 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["The operation lasted too long: It took 4,107 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["Test failed: text expected to contain /Order Confirmation/", 292, 91.25, 5.819051414906337], "isController": false}, {"data": ["The operation lasted too long: It took 5,037 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["The operation lasted too long: It took 3,849 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["The operation lasted too long: It took 3,483 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}, {"data": ["The operation lasted too long: It took 4,335 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, 0.3125, 0.01992825827022718], "isController": false}]}, function(index, item){
        switch(index){
            case 2:
            case 3:
                item = item.toFixed(2) + '%';
                break;
        }
        return item;
    }, [[1, 1]]);

        // Create top5 errors by sampler
    createTable($("#top5ErrorsBySamplerTable"), {"supportsControllersDiscrimination": false, "overall": {"data": ["Total", 5018, 320, "Test failed: text expected to contain /Order Confirmation/", 292, "Test failed: text expected to contain /Shopping Cart/", 12, "The operation lasted too long: It took 4,115 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 5,054 milliseconds, but should not have lasted longer than 5,000 milliseconds.", 1, "The operation lasted too long: It took 4,152 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1], "isController": false}, "titles": ["Sample", "#Samples", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors"], "items": [{"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["1.6 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)", 12, 12, "Test failed: text expected to contain /Order Confirmation/", 12, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": ["3.1 Homepage / (Frontend+Recommendation+AdService)", 400, 3, "The operation lasted too long: It took 5,054 milliseconds, but should not have lasted longer than 5,000 milliseconds.", 1, "The operation lasted too long: It took 6,111 milliseconds, but should not have lasted longer than 5,000 milliseconds.", 1, "The operation lasted too long: It took 5,422 milliseconds, but should not have lasted longer than 5,000 milliseconds.", 1, "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": ["1.5 View Cart /cart (CartService)", 12, 12, "Test failed: text expected to contain /Shopping Cart/", 12, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["1.1 Homepage / (Frontend+Recommendation+AdService)", 15, 4, "The operation lasted too long: It took 5,458 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 4,107 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 4,571 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 3,135 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["2.1 Homepage / (Frontend+Recommendation+AdService)", 100, 9, "The operation lasted too long: It took 4,115 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 4,152 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 6,253 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 5,037 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1, "The operation lasted too long: It took 6,034 milliseconds, but should not have lasted longer than 3,000 milliseconds.", 1], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["2.6 Place Order /cart/checkout (Checkout+Payment+Shipping+Email)", 100, 100, "Test failed: text expected to contain /Order Confirmation/", 100, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["5.2 Checkout with SAVE10 (10% off) (CouponService+Checkout)", 180, 180, "Test failed: text expected to contain /Order Confirmation/", 180, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}]}, function(index, item){
        return item;
    }, [[0, 0]], 0);

});
