$("#btnExecute").click(function(){
	$(this).button('loading').delay(2000).queue(function() {
		$(this).button('reset');
		$(this).dequeue(); 
	});
});