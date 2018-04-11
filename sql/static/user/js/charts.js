var personDataSummary = null;
var personCorlor = [
'rgba(255, 99, 132, 0.9)',
'rgba(54, 162, 235, 0.8)',
'rgba(255, 206, 86, 0.7)',
'rgba(75, 192, 192, 0.8)',
'rgba(153, 102, 255, 0.9)']

$(document).ready(function() {
    var isCharts = window.location.pathname.indexOf("charts");
        if (isCharts != -1) {
        getPersonWork()
        getMonthWork()
    }
});

function getPersonWork(){
    $.ajax({
            type: 'get',
            url: '/getPersonCharts/',
            success: function(data) {
                var data_person = new Array();
                var lb_person = new Array();
                var bg_corlor = new Array()
                for (var i=0; i<data.length; i++) {
                    lb_person.push(data[i][0]);
                    data_person.push(data[i][1]);
                    bg_corlor.push(personCorlor[i%5])
                }

                personDataSummary = {
                labels : lb_person,
                datasets : [
                     {
                        label: '近三个月内个人工单数量龙虎榜TOP 50',
                        data : data_person,
                        backgroundColor:bg_corlor,
                     }
                ]}
                var ctx = document.getElementById("summaryWorkflowByPerson").getContext("2d");
                var myBar = new Chart.Bar(ctx, {data:personDataSummary, options: {
                    scales: {
                        yAxes: [{
                            ticks: {
                                beginAtZero: true
                            }
                        }]
                    }
                }});
            },
            cache: false,
            error: function(XMLHttpRequest, textStatus, errorThrown) {
                alert(errorThrown);
            }
        });
}




function getMonthWork() {
	$.ajax({
		type: 'get',
    	url: '/getMonthCharts/',
    	success: function(data) {
            var data_month = new Array();
            var lb_month = new Array();
            for (var i=0; i<data.length; i++) {
                lb_month.push(data[i][0]);
                data_month.push(data[i][1]);
            }

            console.log(lb_month)
            console.log(data_month)

        var ctx = document.getElementById("summaryWorkflowByMonth").getContext("2d");
        var myChart = new Chart(ctx, {
                                    type: 'line',
                                    data: {
                                        labels: lb_month,
                                        datasets: [{
                                            label: '近三个月内工单数据量',
                                            data: data_month,
                                            backgroundColor: [
                                                'rgba(255, 99, 132, 0.2)',
                                                'rgba(54, 162, 235, 0.2)',
                                                'rgba(255, 206, 86, 0.2)',
                                                'rgba(75, 192, 192, 0.2)',
                                                'rgba(153, 102, 255, 0.2)',
                                                'rgba(255, 159, 64, 0.2)'
                                            ],
                                            borderColor: [
                                                'rgba(255,99,132,1)',
                                                'rgba(54, 162, 235, 1)',
                                                'rgba(255, 206, 86, 1)',
                                                'rgba(75, 192, 192, 1)',
                                                'rgba(153, 102, 255, 1)',
                                                'rgba(255, 159, 64, 1)'
                                            ],
                                            borderWidth: 1
                                        }]
                                    },
                                    options: {
                                        scales: {
                                            yAxes: [{
                                                ticks: {
                                                    beginAtZero:true
                                                }
                                            }]
                                        }
                                    }
                                });

		},
		cache: false,
		error: function(XMLHttpRequest, textStatus, errorThrown) {
            alert(errorThrown);
        }
    });
}
