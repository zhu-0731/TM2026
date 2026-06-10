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

    var data = {"OkPercent": 32.833333333333336, "KoPercent": 67.16666666666667};
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
    createTable($("#apdexTable"), {"supportsControllersDiscrimination": true, "overall": {"data": [0.31833333333333336, 500, 1500, "Total"], "isController": false}, "titles": ["Apdex", "T (Toleration threshold)", "F (Frustration threshold)", "Label"], "items": [{"data": [0.975, 500, 1500, "5. 查看购物车 /cart"], "isController": false}, {"data": [0.0, 500, 1500, "2. 浏览商品 /product/{product_id}"], "isController": false}, {"data": [0.0, 500, 1500, "6. 下单 /cart/checkout"], "isController": false}, {"data": [0.0, 500, 1500, "4. 添加购物车 /cart"], "isController": false}, {"data": [0.935, 500, 1500, "1. 访问首页 /"], "isController": false}, {"data": [0.0, 500, 1500, "3. 设置货币 /setCurrency"], "isController": false}]}, function(index, item){
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
    createTable($("#statisticsTable"), {"supportsControllersDiscrimination": true, "overall": {"data": ["Total", 600, 403, 67.16666666666667, 72.05499999999999, 3, 2823, 10.0, 155.89999999999998, 282.74999999999966, 1556.4000000000015, 6.797095374576598, 33.38040926656509, 2.7084942628266857], "isController": false}, "titles": ["Label", "#Samples", "FAIL", "Error %", "Average", "Min", "Max", "Median", "90th pct", "95th pct", "99th pct", "Transactions/s", "Received", "Sent"], "items": [{"data": ["5. 查看购物车 /cart", 100, 0, 0.0, 101.74999999999993, 16, 1634, 31.0, 179.20000000000005, 232.69999999999993, 1631.6399999999987, 1.2135185971725015, 8.335237356653115, 0.37803948486135547], "isController": false}, {"data": ["2. 浏览商品 /product/{product_id}", 100, 100, 100.0, 13.189999999999996, 3, 166, 6.0, 16.700000000000017, 57.5499999999999, 165.7899999999999, 1.2073649260488981, 0.2075158466646544, 0.3808387413220646], "isController": false}, {"data": ["6. 下单 /cart/checkout", 100, 100, 100.0, 15.479999999999993, 4, 156, 7.5, 28.50000000000003, 94.89999999999998, 155.56999999999977, 1.2208372501861777, 4.951746884575942, 0.766945697922135], "isController": false}, {"data": ["4. 添加购物车 /cart", 100, 100, 100.0, 10.389999999999999, 4, 104, 7.0, 16.900000000000006, 26.94999999999999, 103.82999999999991, 1.2165154132502858, 4.832797559670081, 0.5062795004987714], "isController": false}, {"data": ["1. 访问首页 /", 100, 3, 3.0, 282.02000000000004, 37, 2823, 138.0, 452.4000000000003, 1534.8999999999946, 2817.7299999999973, 1.1808745556959483, 12.311770440938558, 0.3561074832020594], "isController": false}, {"data": ["3. 设置货币 /setCurrency", 100, 100, 100.0, 9.500000000000002, 4, 93, 7.0, 14.0, 18.94999999999999, 92.87999999999994, 1.2014032389831324, 4.770415595415445, 0.502149010043731], "isController": false}]}, function(index, item){
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
    createTable($("#errorsTable"), {"supportsControllersDiscrimination": false, "titles": ["Type of error", "Number of errors", "% in errors", "% in all samples"], "items": [{"data": ["The operation lasted too long: It took 2,197 milliseconds, but should not have lasted longer than 2,000 milliseconds.", 1, 0.24813895781637718, 0.16666666666666666], "isController": false}, {"data": ["The operation lasted too long: It took 2,823 milliseconds, but should not have lasted longer than 2,000 milliseconds.", 1, 0.24813895781637718, 0.16666666666666666], "isController": false}, {"data": ["The operation lasted too long: It took 2,296 milliseconds, but should not have lasted longer than 2,000 milliseconds.", 1, 0.24813895781637718, 0.16666666666666666], "isController": false}, {"data": ["500/Internal Server Error", 7, 1.7369727047146402, 1.1666666666666667], "isController": false}, {"data": ["422/Unprocessable Entity", 293, 72.70471464019852, 48.833333333333336], "isController": false}, {"data": ["404/Not Found", 100, 24.81389578163772, 16.666666666666668], "isController": false}]}, function(index, item){
        switch(index){
            case 2:
            case 3:
                item = item.toFixed(2) + '%';
                break;
        }
        return item;
    }, [[1, 1]]);

        // Create top5 errors by sampler
    createTable($("#top5ErrorsBySamplerTable"), {"supportsControllersDiscrimination": false, "overall": {"data": ["Total", 600, 403, "422/Unprocessable Entity", 293, "404/Not Found", 100, "500/Internal Server Error", 7, "The operation lasted too long: It took 2,197 milliseconds, but should not have lasted longer than 2,000 milliseconds.", 1, "The operation lasted too long: It took 2,823 milliseconds, but should not have lasted longer than 2,000 milliseconds.", 1], "isController": false}, "titles": ["Sample", "#Samples", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors"], "items": [{"data": [], "isController": false}, {"data": ["2. 浏览商品 /product/{product_id}", 100, 100, "404/Not Found", 100, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["6. 下单 /cart/checkout", 100, 100, "422/Unprocessable Entity", 93, "500/Internal Server Error", 7, "", "", "", "", "", ""], "isController": false}, {"data": ["4. 添加购物车 /cart", 100, 100, "422/Unprocessable Entity", 100, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["1. 访问首页 /", 100, 3, "The operation lasted too long: It took 2,197 milliseconds, but should not have lasted longer than 2,000 milliseconds.", 1, "The operation lasted too long: It took 2,823 milliseconds, but should not have lasted longer than 2,000 milliseconds.", 1, "The operation lasted too long: It took 2,296 milliseconds, but should not have lasted longer than 2,000 milliseconds.", 1, "", "", "", ""], "isController": false}, {"data": ["3. 设置货币 /setCurrency", 100, 100, "422/Unprocessable Entity", 100, "", "", "", "", "", "", "", ""], "isController": false}]}, function(index, item){
        return item;
    }, [[0, 0]], 0);

});
