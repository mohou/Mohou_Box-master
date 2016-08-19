/*
	前端 zhuyan 2014.12.04
*/
// JSON2 by Douglas Crockford (minified).
//var JSON;JSON||(JSON={}),function(){function str(a,b){var c,d,e,f,g=gap,h,i=b[a];i&&typeof i=="object"&&typeof i.toJSON=="function"&&(i=i.toJSON(a)),typeof rep=="function"&&(i=rep.call(b,a,i));switch(typeof i){case"string":return quote(i);case"number":return isFinite(i)?String(i):"null";case"boolean":case"null":return String(i);case"object":if(!i)return"null";gap+=indent,h=[];if(Object.prototype.toString.apply(i)==="[object Array]"){f=i.length;for(c=0;c<f;c+=1)h[c]=str(c,i)||"null";e=h.length===0?"[]":gap?"[\n"+gap+h.join(",\n"+gap)+"\n"+g+"]":"["+h.join(",")+"]",gap=g;return e}if(rep&&typeof rep=="object"){f=rep.length;for(c=0;c<f;c+=1)typeof rep[c]=="string"&&(d=rep[c],e=str(d,i),e&&h.push(quote(d)+(gap?": ":":")+e))}else for(d in i)Object.prototype.hasOwnProperty.call(i,d)&&(e=str(d,i),e&&h.push(quote(d)+(gap?": ":":")+e));e=h.length===0?"{}":gap?"{\n"+gap+h.join(",\n"+gap)+"\n"+g+"}":"{"+h.join(",")+"}",gap=g;return e}}function quote(a){escapable.lastIndex=0;return escapable.test(a)?'"'+a.replace(escapable,function(a){var b=meta[a];return typeof b=="string"?b:"\\u"+("0000"+a.charCodeAt(0).toString(16)).slice(-4)})+'"':'"'+a+'"'}function f(a){return a<10?"0"+a:a}"use strict",typeof Date.prototype.toJSON!="function"&&(Date.prototype.toJSON=function(a){return isFinite(this.valueOf())?this.getUTCFullYear()+"-"+f(this.getUTCMonth()+1)+"-"+f(this.getUTCDate())+"T"+f(this.getUTCHours())+":"+f(this.getUTCMinutes())+":"+f(this.getUTCSeconds())+"Z":null},String.prototype.toJSON=Number.prototype.toJSON=Boolean.prototype.toJSON=function(a){return this.valueOf()});var cx=/[\u0000\u00ad\u0600-\u0604\u070f\u17b4\u17b5\u200c-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufff0-\uffff]/g,escapable=/[\\\"\x00-\x1f\x7f-\x9f\u00ad\u0600-\u0604\u070f\u17b4\u17b5\u200c-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufff0-\uffff]/g,gap,indent,meta={"\b":"\\b","\t":"\\t","\n":"\\n","\f":"\\f","\r":"\\r",'"':'\\"',"\\":"\\\\"},rep;typeof JSON.stringify!="function"&&(JSON.stringify=function(a,b,c){var d;gap="",indent="";if(typeof c=="number")for(d=0;d<c;d+=1)indent+=" ";else typeof c=="string"&&(indent=c);rep=b;if(!b||typeof b=="function"||typeof b=="object"&&typeof b.length=="number")return str("",{"":a});throw new Error("JSON.stringify")}),typeof JSON.parse!="function"&&(JSON.parse=function(text,reviver){function walk(a,b){var c,d,e=a[b];if(e&&typeof e=="object")for(c in e)Object.prototype.hasOwnProperty.call(e,c)&&(d=walk(e,c),d!==undefined?e[c]=d:delete e[c]);return reviver.call(a,b,e)}var j;text=String(text),cx.lastIndex=0,cx.test(text)&&(text=text.replace(cx,function(a){return"\\u"+("0000"+a.charCodeAt(0).toString(16)).slice(-4)}));if(/^[\],:{}\s]*$/.test(text.replace(/\\(?:["\\\/bfnrt]|u[0-9a-fA-F]{4})/g,"@").replace(/"[^"\\\n\r]*"|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g,"]").replace(/(?:^|:|,)(?:\s*\[)+/g,""))){j=eval("("+text+")");return typeof reviver=="function"?walk({"":j},""):j}throw new SyntaxError("JSON.parse")})}()

$(function(){
	
	//验证输入密码与确定密码是否一致
	$("#passwordText").blur(function(){
		if($(this).val().length > 0){
			//alert("ok")
		}else{
			alert("SSID不能为空");
			$("#passwordText").focus()
		}
	})
	
	$("#passwordInput1").blur(function(){
		if($(this).val().length > 0){
			//alert("ok")
		}else{
			alert("密码不能为空");
			$("#passwordInput1").focus()
		}
	})
	$("#passwordInput2").blur(function(){
		if($(this).val().length > 0){
			if($("#passwordInput2").val() != $("#passwordInput1").val()){
				alert("两次输入的密码不一致")
			}else{
				//alert("ok")
			}
		}else{
			alert("确认密码不能为空");
			$("#passwordInput2").focus()
		}
	})
	//第一步页面中 显示连接按钮
	$('.main_body tr.show').removeClass('show').addClass('hide');	
		
	$(document).on('click','.main_body .tr',function(){
		clearTimeout(timeout_wifiinfo)
		$('.main_body tr.show').removeClass('show').addClass('hide');		
		$(this).next('.hide').addClass('show');
	})
	
	/*刷新页面*/    
	$("#shuaxin").click(function(){
		requestWifiInfo();
	})

	//输入密码弹出框
	$(".closeBtn").click(function(){
		timeout_wifiinfo = setTimeout(requestWifiInfo, 5000);
		$('#passwordBox .passwordInput').attr('pid','')
		$("#passwordBox").css({position:'absolute', top: ($(window).height() - $("#passwordBox").outerHeight())/2 + $(document).scrollTop()});
		$(".mask").css({position:'absolute', top: ($(window).height() - $(".mask").outerHeight())/2 + $(document).scrollTop()});
		$("#passwordBox").fadeOut();
		$(".mask").fadeOut();
	})
	
	$(".submitBtn").click(function(){
		var zhi = $(this).parent().parent().children().children('.passwordInput').val().length;
		if( zhi < 8 || zhi > 64){
			alert('长度必须为8-64字符');
		}else{
			timeout_wifiinfo = setTimeout(requestWifiInfo, 5000);
			$("#passwordBox").css({position:'absolute', top: ($(window).height() - $("#passwordBox").outerHeight())/2 + $(document).scrollTop()});
			$(".mask").css({position:'absolute', top: ($(window).height() - $(".mask").outerHeight())/2 + $(document).scrollTop()});
			$("#passwordBox").fadeOut();
			$(".mask").fadeOut();
			setwifi();
		}
	})
	
	$(document).on('click','.linkBtn',function(){
		var lock = $(this).parent().parent().prev().find("input[name='wifi_lock']").val();
		if (lock == "on"){
			$("#passwordBox .passwordInput").val('')
			$('#passwordBox .passwordInput').attr('pid',$(this).parent().parent().prev().find($('.linkName')).text())
			$("#connect_ssid").val($('#passwordBox .passwordInput').attr('pid'));
			$("#passwordBox").fadeIn().css({position:'absolute', top: ($(window).height() - $("#passwordBox").outerHeight())/2 + $(document).scrollTop()});;
			$(".mask").fadeIn().css({position:'absolute', top: ($(window).height() - $(".mask").outerHeight())/2 + $(document).scrollTop()});			
		}
		else {
			timeout_wifiinfo = setTimeout(requestWifiInfo, 5000);
			$('#passwordBox .passwordInput').attr('pid',$(this).parent().parent().prev().find($('.linkName')).text());
			setwifi();
		}
	})


	$(".box input[type='checkbox']").change(function(){
		if ($(this).prop('checked')) {
			$(this).attr('value', 'True');
		}
		else {
			$(this).attr('value', 'False');
		}
	})
	
	$("#show_passwd").change(function(){
		if ($(this).prop('checked')) {
			$("#password").attr('type', 'text');
		}
		else {
			$("#password").attr('type', 'password');
		}
	})
	//页面跳转js 开始
	//点击下一步
	//$(".wifi_conn h2").click(function(){ 
	$(document).on("click",".wifi_conn h2",function(){	
		if($(".wifi_conn .main_body").is(":hidden")){ 
			$(".wifi_conn .main_body").show();
			$(".wifi_conn h2").removeAttr('style');
			$(".wifi_conn h2 span").html(" [ ↑ ]")
		}else{ 
			$(".wifi_conn .main_body").hide();
			$(".wifi_conn h2").css('margin-bottom','10px');
			$(".wifi_conn h2 span").html(" [ ↓ ]")
		}	
	})

	$(document).on("click",".wifi_setting h2",function(){	
		if($(".wifi_setting .main_body").is(":hidden")){ 
			$(".wifi_setting .main_body").show();
			$(".wifi_setting h2").removeAttr('style');
			$(".wifi_setting h2 span").html(" [ ↑ ]")
		}else{ 
			$(".wifi_setting .main_body").hide();
			$(".wifi_setting h2").css('margin-bottom','10px');
			$(".wifi_setting h2 span").html(" [ ↓ ]")
		}	
	})
	$(document).on("click",".wire_setting h2",function(){	
		if($(".wire_setting .main_body").is(":hidden")){ 
			$(".wire_setting .main_body").show();
			$(".wire_setting h2").removeAttr('style');
			$(".wire_setting h2 span").html(" [ ↑ ]")
		}else{ 
			$(".wire_setting .main_body").hide();
			$(".wire_setting h2").css('margin-bottom','10px');
			$(".wire_setting h2 span").html(" [ ↓ ]")
		}	
	})
	$(document).on("click",".serial_setting h2",function(){	
		if($(".serial_setting .main_body").is(":hidden")){ 
			$(".serial_setting .main_body").show();
			$(".serial_setting h2").removeAttr('style');
			$(".serial_setting h2 span").html(" [ ↑ ]")
		}else{ 
			$(".serial_setting .main_body").hide();
			$(".serial_setting h2").css('margin-bottom','10px');
			$(".serial_setting h2 span").html(" [ ↓ ]")
		}	
	})
	/*
	$(document).on("click",".bind_setting h2",function(){	
		if($(".bind_setting .main_body").is(":hidden")){ 
			$(".bind_setting .main_body").show();
			$(".bind_setting h2").removeAttr('style');
			$(".bind_setting h2 span").html(" [ ↑ ]")
		}else{ 
			$(".bind_setting .main_body").hide();
			$(".bind_setting h2").css('margin-bottom','10px');
			$(".bind_setting h2 span").html(" [ ↓ ]")
		}	
	})

	$(document).on("click",".print_setting h2",function(){	
		if($(".print_setting .main_body").is(":hidden")){ 
			$(".print_setting .main_body").show();
			$(".print_setting h2").removeAttr('style');
			$(".print_setting h2 span").html(" [ ↑ ]")
		}else{ 
			$(".print_setting .main_body").hide();
			$(".print_setting h2").css('margin-bottom','10px');
			$(".print_setting h2 span").html(" [ ↓ ]")
		}	
	})
	
	$(document).on("click",".slicer_base_setting h2",function(){	
		if($(".slicer_base_setting .main_body").is(":hidden")){ 
			$(".slicer_base_setting .main_body").show();
			$(".slicer_base_setting h2").removeAttr('style');
			$(".slicer_base_setting h2 span").html(" [ ↑ ]")
		}else{ 
			$(".slicer_base_setting .main_body").hide();
			$(".slicer_base_setting h2").css('margin-bottom','10px');
			$(".slicer_base_setting h2 span").html(" [ ↓ ]")
		}	
	})

	$(document).on("click",".slicer_adv_setting h2",function(){	
		if($(".slicer_adv_setting .main_body").is(":hidden")){ 
			$(".slicer_adv_setting .main_body").show();
			$(".slicer_adv_setting h2").removeAttr('style');
			$(".slicer_adv_setting h2 span").html(" [ ↑ ]")
		}else{ 
			$(".slicer_adv_setting .main_body").hide();
			$(".slicer_adv_setting h2").css('margin-bottom','10px');
			$(".slicer_adv_setting h2 span").html(" [ ↓ ]")
		}	
	})*/

	/*if ($("#bindBtn").length > 0) {
		$("#bindBtn").click(bindAccount)
	}
	if ($("#unbindBtn").length > 0) {
		$("#unbindBtn").click(unbindAccount)
	}*/

	$("#wifi_endBtn").click(set_wifi_ip)
	$("#wire_endBtn").click(set_wire_ip)
	$("#serial_endBtn").click(set_serial_number)
	/*$("#print_endBtn").click(set_print_info)
	$("#slicer_base_endBtn").click(set_print_info)
	$("#slicer_adv_endBtn").click(set_print_info)
	*/

	if($('.wifi input[type=radio]:checked').attr('onOff') == 4){
		$(".wifi .subItem label").css('color','#000');
		$(".wifi .subItem").find('input:text').removeAttr('disabled');
	}else if($('.wifi input[type=radio]:checked').attr('onOff') == 3){ 
		$(".wifi .subItem label").css('color','#969696');
		$(".wifi .subItem").find('input:text').attr('disabled','disabled');
	}	
	$(".wifi_setting input:radio").change(function(){
		if($(this).attr('onOff') == 3){
			$(this).parents().next().next('.subItem').find('input:text').attr('disabled','disabled');
			$(".wifi .subItem label").css('color','#969696');
		}
		if($(this).attr('onOff') == 4){
			$(".wifi .subItem label").css('color','#000');
			$(".wifi .subItem").find('input:text').removeAttr('disabled');
		}else{
			$(this).parents().next('.subItem').find('input:text').removeAttr('disabled');
		}
	})

	if($('.wire input[type=radio]:checked').attr('onOff') == 4){
		$(".wire .subItem").find('input:text').removeAttr('disabled');
		$(".wire .subItem label").css('color','#000');
	}else if($('.wifi input[type=radio]:checked').attr('onOff') == 3){ 
		$(".wire .subItem").find('input:text').attr('disabled','disabled');
		$(".wire .subItem label").css('color','#969696');
	}	
	$(".wire_setting input:radio").change(function(){
		if($(this).attr('onOff') == 3){
			$(this).parents().next().next('.subItem').find('input:text').attr('disabled','disabled');
			$(".wire .subItem label").css('color','#969696');
		}
		if($(this).attr('onOff') == 4){
			$(".wire .subItem label").css('color','#000');
			$(".wire .subItem").find('input:text').removeAttr('disabled');
		}else{
			$(this).parents().next('.subItem').find('input:text').removeAttr('disabled');
		}
	})
	extruder_amount_change();
	$('#extruder_amount').change(extruder_amount_change);
	$('#machine_type').change( function() {
		var machine_type = $.trim($('#machine_type').val());
		var request_data = {
				
							"machine_name" : "Default",
							"machine_type": machine_type
					};
		jQuery.ajax({
            url: "settings/machines",
            type: "POST",
            contentType: "application/json; charset=UTF-8",
            dataType: "json",
            data: JSON.stringify(request_data),
            success: function(response) {
            	set_alter_print_info(response);
	        }
        });

	});
})


function checkKeyCode(e){ 
 	var key = window.event ? e.keyCode : e.which;	
	if (key<48 || key>57)	{
 		if(window.event)   
        	e.returnValue = false; //这是IE的   
     	else  
         	e.preventDefault(); //这是FireFox的  
	}
	//alert(event.keyCode);
 }
 
 function checkText1(id1,id2,e){
 	var key = window.event ? e.keyCode : e.which;	
	var tb1 = document.getElementById(id1);
	var tb2 = document.getElementById(id2);
 	//checkValue=document.getElementById(id);
 	if((tb1.value.length==3)||((key==110||key==190)&&(tb1.value.length !=0))){
		if(tb1.value>223){
			alert(tb1.value+"不是有效项，请指定一个介于1和223间的值。");
			tb1.value=223;
			tb1.focus();
		}else{
			tb2.focus();
			tb2.select();
		}
	}
 }
 
 
 function checkText2(id2,id3,e){
 	var key = window.event ? e.keyCode : e.which;
	var tb2 = document.getElementById(id2);
	var tb3 = document.getElementById(id3);
 	//checkValue=document.getElementById(id);
 	 if((tb2.value.length==3)||((key==110||key==190)&&(tb2.value.length !=0))){
	 	if(tb2.value>255){
			alert(tb2.value+"不是有效项，请指定一个介于1和255间的值。");
			tb2.value=255;
			tb2.focus();
		}else{
			tb3.focus();
			tb3.select();
		}
	}
	
 }
 
 
 function checkText3(id3,id4,e){
 	var key = window.event ? e.keyCode : e.which;
 	var tb3 = document.getElementById(id3);
	var tb4 = document.getElementById(id4);
	
 	if((tb3.value.length==3)||((key==110||key==190)&&(tb3.value.length !=0))){
		if(tb3.value>255){
			alert(tb3.value+"不是有效项，请指定一个介于1和255间的值。");
			tb3.value=255;
			tb3.focus();
		}else{
			tb4.focus();
			tb4.select();
		}
	}
	
 }
 

 function checkText4(id3,id4,e){
	var key = window.event ? e.keyCode : e.which;
	var tb4 = document.getElementById(id3);
	var sm21 = document.getElementById(id4);

	if((tb4.value.length==3)||((key==110||key==190)&&(tb4.value.length !=0))){
		if(tb4.value>255){
			alert(tb4.value+"不是有效项，请指定一个介于1和255间的值。");
			tb4.value=255;
			tb4.focus();
		}else{
			sm21.focus();
			sm21.select();
		}
	
	}
	
 }
 
  function checkText4(id3,id4,e){
	var key = window.event ? e.keyCode : e.which;
	var tb4 = document.getElementById(id3);
	var sm21 = document.getElementById(id4);

	if((tb4.value.length==3)||((key==110||key==190)&&(tb4.value.length !=0))){
		if(tb4.value>255){
			alert(tb4.value+"不是有效项，请指定一个介于1和255间的值。");
			tb4.value=255;
			tb4.focus();
		}else{
			sm21.focus();
			sm21.select();
		}
	
	}
	
 }
 

function checkText5(id2,id3,e){
 	var key = window.event ? e.keyCode : e.which;
	var tb2 = document.getElementById(id2);
	var tb3 = document.getElementById(id3);
 	//checkValue=document.getElementById(id);
 	 if((tb2.value.length==3)||((key==110||key==190)&&(tb2.value.length !=0))){
	 	if(tb2.value>255){
			alert(tb2.value+"不是有效项，请指定一个介于1和255间的值。");
			tb2.value=255;
			tb2.focus();
		}else{
			tb3.focus();
			tb3.select();
		}
	}
	
 }



timeout_wifiinfo = setTimeout(requestWifiInfo(), 1000);

 function requestWifiInfo() {
    jQuery.get('mowifiinfoajax', {},
        function(data, status, xhr) {
			$("#wifi_table").html(data);
            //document.getElementById("wifi_table").innerHTML=data;
            $("#wifi_table tbody .tr:odd").css('background','#eff3f5');
            clearTimeout(timeout_wifiinfo);
            timeout_wifiinfo = setTimeout(requestWifiInfo, 5000);
        }
    );
 }
 
 function hidden_all(){
	 $(".wifi_conn").hide();
	 $(".wifi_setting").hide();
	 $(".wire_setting").hide();
	 $(".serial_setting").hide();
	 /* $(".bind_setting").hide(); 
	 $(".print_setting").hide();
	 $(".slicer_base_setting").hide();
	 $(".slicer_adv_setting").hide();*/
 }
 
 function show_prepare(title, message){
	 $(".success").css("color","#72c736");
	 $(".success").text(message);
	 $(".messages h2").text(title);
	 $(".messages").show();
 }
 
 function show_response(data){
	 $(".success").text(data.msg);
	 if (data.result == 0) {
		 $(".success").css("color","#72c736");
	 }
	 else {
		 $(".success").css("color","red");
	 }
	 $(".messages").show();
 }
 
 function set_alter_print_info(response) {
	 if (response.result ==0) {
		 $('#machine_width').val(response.data.machine_width);
		 $('#machine_depth').val(response.data.machine_depth);
		 $('#machine_height').val(response.data.machine_height);
		 $('#machine_center_is_zero').val(response.data.machine_center_is_zero);
		 $('#has_heated_bed').val(response.data.has_heated_bed);
		 machine_shape_list = {};
		 for (value in response.data.machine_shape) {
			 machine_shape_list[response.data.machine_shape[value]] = response.data.machine_shape[value];
		 }
		 var machine_shap_output = [];
		 $.each(machine_shape_list, function(key, value)
		 {
			 machine_shap_output.push('<option value="'+ key +'">'+ value +'</option>');
		 });

		 $('#machine_shape').html(machine_shap_output.join(''));

		 extruder_amount_list = {};
		 for (value in response.data.extruder_amount) {
			 extruder_amount_list[response.data.extruder_amount[value]] = response.data.extruder_amount[value];
		 }
		 var extruder_amount_output = [];
		 $.each(extruder_amount_list, function(key, value)
		 {
			 extruder_amount_output.push('<option value="'+ key +'">'+ value +'</option>');
		 });

		 $('#extruder_amount').html(extruder_amount_output.join(''));
		 
		 $('#extruder_offset_x2').val(response.data.extruder_offset_x2);
		 $('#extruder_offset_y2').val(response.data.extruder_offset_y2);
		 $('#extruder_head_size_min_x').val(response.data.extruder_head_size_min_x);
		 $('#extruder_head_size_min_y').val(response.data.extruder_head_size_min_y);
		 $('#extruder_head_size_max_x').val(response.data.extruder_head_size_max_x);
		 $('#extruder_head_size_max_y').val(response.data.extruder_head_size_max_y);
		 $('#extruder_head_size_height').val(response.data.extruder_head_size_height);
		 
		 $('#filament_diameter').val(response.data.filament_diameter);
		 $('#filament_diameter2').val(response.data.filament_diameter2);
		 $('#nozzle_size').val(response.data.nozzle_size);
		 
		 $('#layer_height').val(response.data.layer_height);
		 $('#wall_thickness').val(response.data.wall_thickness);
		 $('#bottom_thickness').val(response.data.bottom_thickness);
		 $('#layer0_width_factor').val(response.data.layer0_width_factor);
		 $('#object_sink').val(response.data.object_sink);
		 $('#overlap_dual').val(response.data.overlap_dual);
		 $('#retraction_enable').val(response.data.retraction_enable);
		 $('#retraction_min_travel').val(response.data.retraction_min_travel);
		 retraction_combing_list = {};
		 for (value in response.data.retraction_combing) {
			 retraction_combing_list[response.data.retraction_combing[value]] = response.data.retraction_combing[value];
		 }
		 var retraction_combing_output = [];
		 $.each(retraction_combing_list, function(key, value)
		 {
			 retraction_combing_output.push('<option value="'+ key +'">'+ value +'</option>');
		 });

		 $('#retraction_combing').html(retraction_combing_output.join(''));
		 
		 $('#retraction_minimal_extrusion').val(response.data.retraction_minimal_extrusion);
		 $('#retraction_hop').val(response.data.retraction_hop);
		 $('#retraction_speed').val(response.data.retraction_speed);
		 $('#retraction_amount').val(response.data.retraction_amount);
		 
		 $('#solid_layer_thickness').val(response.data.solid_layer_thickness);
		 $('#fill_density').val(response.data.fill_density);
		 $('#solid_top').val(response.data.solid_top);
		 $('#solid_bottom').val(response.data.solid_bottom);
		 $('#fill_overlap').val(response.data.fill_overlap);
		 $('#print_speed').val(response.data.print_speed);
		 $('#print_temperature').val(response.data.print_temperature);
		 $('#print_temperature2').val(response.data.print_temperature2);
		 $('#print_bed_temperature').val(response.data.print_bed_temperature);
		 $('#travel_speed').val(response.data.travel_speed);
		 $('#bottom_layer_speed').val(response.data.bottom_layer_speed);
		 $('#infill_speed').val(response.data.infill_speed);
		 $('#solidarea_speed').val(response.data.solidarea_speed);
		 $('#inset0_speed').val(response.data.inset0_speed);
		 $('#insetx_speed').val(response.data.insetx_speed);
		 
		 support_list = {};
		 for (value in response.data.support) {
			 support_list[response.data.support[value]] = response.data.support[value];
		 }
		 var support_output = [];
		 $.each(support_list, function(key, value)
		 {
			 support_output.push('<option value="'+ key +'">'+ value +'</option>');
		 });

		 $('#support').html(support_output.join(''));
		 
		 support_type_list = {};
		 for (value in response.data.support_type) {
			 support_type_list[response.data.support_type[value]] = response.data.support_type[value];
		 }
		 var support_type_output = [];
		 $.each(support_type_list, function(key, value)
		 {
			 support_type_output.push('<option value="'+ key +'">'+ value +'</option>');
		 });

		 $('#support_type').html(support_type_output.join(''));
		 
		 $('#support_angle').val(response.data.support_angle);
		 $('#support_fill_rate').val(response.data.support_fill_rate);
		 $('#support_xy_distance').val(response.data.support_xy_distance);
		 $('#support_z_distance').val(response.data.support_z_distance);
		 
		 platform_adhesion_list = {};
		 for (value in response.data.platform_adhesion) {
			 platform_adhesion_list[response.data.platform_adhesion[value]] = response.data.platform_adhesion[value];
		 }
		 var platform_adhesion_output = [];
		 $.each(platform_adhesion_list, function(key, value)
		 {
			 platform_adhesion_output.push('<option value="'+ key +'">'+ value +'</option>');
		 });

		 $('#platform_adhesion').html(platform_adhesion_output.join(''));
		 
		 $('#skirt_line_count').val(response.data.skirt_line_count);
		 $('#skirt_gap').val(response.data.skirt_gap);
		 $('#skirt_minimal_length').val(response.data.skirt_minimal_length);
		 $('#brim_line_count').val(response.data.brim_line_count);
		 $('#raft_margin').val(response.data.raft_margin);
		 $('#raft_line_spacing').val(response.data.raft_line_spacing);
		 $('#raft_base_thickness').val(response.data.raft_base_thickness);
		 $('#raft_base_linewidth').val(response.data.raft_base_linewidth);
		 $('#raft_interface_thickness').val(response.data.raft_interface_thickness);
		 $('#raft_interface_linewidth').val(response.data.raft_interface_linewidth);
		 $('#raft_airgap_all').val(response.data.raft_airgap_all);
		 $('#raft_airgap').val(response.data.raft_airgap);
		 $('#raft_surface_layers').val(response.data.raft_surface_layers);
		 $('#raft_surface_thickness').val(response.data.raft_surface_thickness);
		 $('#raft_surface_linewidth').val(response.data.raft_surface_linewidth);
		 
		 $('#cool_min_layer_time').val(response.data.cool_min_layer_time);
		 $('#fan_enabled').val(response.data.fan_enabled);
		 $('#fan_full_height').val(response.data.fan_full_height);
		 $('#fan_speed').val(response.data.fan_speed);
		 $('#fan_speed_max').val(response.data.fan_speed_max);
		 $('#cool_min_feedrate').val(response.data.cool_min_feedrate);
		 $('#cool_head_lift').val(response.data.cool_head_lift);

		 extruder_amount_change();
		$(".box input[type='checkbox']").each(function(){
			if ($(this).val() == "True") {
				$(this).attr('checked', 'true');
			}
			else {
				$(this).removeAttr('checked');
			}
		})
	 }
	 else {
		 alert("Error!");
	 }
 }
 
 function setwifi() {
    wifissid = $("#passwordBox .passwordInput").attr('pid');
    wifipwd = $("#passwordBox .passwordInput").val()
    jQuery.post('mowifiinfoajax', {type:1, wifissid:wifissid, wifipwd:wifipwd},
        function(data, status, xhr) {
            //alert(data);
        }
    );
 }
 
 function set_wifi_ip() {
	var wifi_dhcp = $("input[name='wifi_radio']:checked").attr('zt');
	var wifi_ip = $("#wifi_ip_sec1").val()+"."+$("#wifi_ip_sec2").val()+"."+$("#wifi_ip_sec3").val()+"."+$("#wifi_ip_sec4").val();
	var wifi_mask = $("#wifi_mask_sec1").val()+"."+$("#wifi_mask_sec2").val()+"."+$("#wifi_mask_sec3").val()+"."+$("#wifi_mask_sec4").val();
	var wifi_gateway = $("#wifi_gateway_sec1").val()+"."+$("#wifi_gateway_sec2").val()+"."+$("#wifi_gateway_sec3").val()+"."+$("#wifi_gateway_sec4").val();
	var wifi_dns = $("#wifi_dns_sec1").val()+"."+$("#wifi_dns_sec2").val()+"."+$("#wifi_dns_sec3").val()+"."+$("#wifi_dns_sec4").val();

	hidden_all();
	show_prepare("无线网络设置", "设置中...")
	jQuery.post('mowifiinfoajax', {type:2, dhcp:wifi_dhcp, ip:wifi_ip, mask:wifi_mask, gateway:wifi_gateway, dns:wifi_dns},
        function(data, status, xhr) {
            if (data == 0) {
            	$(".success").text("设置成功");
            	$(".success").css("color","#72c736");
            }
            else {
            	$(".success").text("设置失败");
            	$(".success").css("color","red");
            }
        }
    );
}

 function set_wire_ip() {
	var wire_dhcp = $("input[name='wire_radio']:checked").attr('zt');
	var wire_ip = $("#wire_ip_sec1").val()+"."+$("#wire_ip_sec2").val()+"."+$("#wire_ip_sec3").val()+"."+$("#wire_ip_sec4").val();
	var wire_mask = $("#wire_mask_sec1").val()+"."+$("#wire_mask_sec2").val()+"."+$("#wire_mask_sec3").val()+"."+$("#wire_mask_sec4").val();
	var wire_gateway = $("#wire_gateway_sec1").val()+"."+$("#wire_gateway_sec2").val()+"."+$("#wire_gateway_sec3").val()+"."+$("#wire_gateway_sec4").val();
	var wire_dns = $("#wire_dns_sec1").val()+"."+$("#wire_dns_sec2").val()+"."+$("#wire_dns_sec3").val()+"."+$("#wire_dns_sec4").val();

	hidden_all();
	show_prepare("有线网络设置", "设置中...")
	jQuery.post('mowifiinfoajax', {type:3, dhcp:wire_dhcp, ip:wire_ip, mask:wire_mask, gateway:wire_gateway, dns:wire_dns},
        function(data, status, xhr) {
	        if (data == 0) {
	        	$(".success").text("设置成功");
	        	$(".success").css("color","#72c736");
	        }
	        else {
	        	$(".success").text("设置失败");
	        	$(".success").css("color","red");
	        }
        }
    );
 }
 function set_serial_number() {
		var serial_number = $("#serial_number").val();
		if(serial_number.length != 32){
			alert("序列号必须为32位字母或数字。");
			return false;
		}
		hidden_all();
		show_prepare("注册序列号", "设置中...")
		$(".success").text("设置成功。盒子的WIFI热点变更为：mohou_" + serial_number.substring(20,24) + ", 密码为：mohouhezi。");
		$(".success").css("color","#72c736");
		jQuery.post('setserialnumber', {sn:serial_number},
	        function(data, status, xhr) {
		        //if (data == 0) {
		        /*}
		        else {
		        	$(".success").text("设置失败");
		        	$(".success").css("color","red");
		        }*/
	        }
	    );
}
 function bindAccount() {
	var username = $("#username").val();
	var password = $("#passwd").val();
	var device_id = $("#device_id").val();
	if(username.length == 0){
		alert("账号不能为空");
		$("#username").focus();
		return false;
	}
	if(password.length == 0){
		alert("密码不能为空");
		$("#password").focus();
		return false;
	}
	hidden_all();
	show_prepare("绑定账号", "绑定中...");
	jQuery.post('bind', {username:username, password:password, device_id:device_id},
        function(data, status, xhr) {
			show_response(data);
        }
    );
}
 function unbindAccount() {
	var name = $("#username").val();
	var device_id = $("#device_id").val();

	hidden_all();
	show_prepare("解除绑定账号", "解绑中...");
	jQuery.post('unbind', {username:name, device_id:device_id},
        function(data, status, xhr) {
			show_response(data);
        }
    );
}
 
 function set_print_info() {
	var machine_type_changed = 0;
	if ($('#machine_type').val() != $('#machine_type_default').val()) {
		machine_type_changed = 1
	}
	var request_data = {
	   "serial": {
			"port": $('#serial_port').val(),
			"baudrate": $('#serial_baud').val()
	    },
	   "data_add": {
	        "print_mode": 2,
	        "filament_diameter": $('#filament_diameter').val(),
	        "filament_diameter2": $('#filament_diameter2').val(),
	        "filament_flow": $('#filament_flow').val(),
	        "nozzle_size": $('#nozzle_size').val(),
	        
        	"layer_height": $('#layer_height').val(),
        	"wall_thickness": $('#wall_thickness').val(),
        	"bottom_thickness": $('#bottom_thickness').val(),
        	"layer0_width_factor": $('#layer0_width_factor').val(),
        	"object_sink": $('#object_sink').val(),
        	"overlap_dual": $('#overlap_dual').val(),
        	"retraction_enable": $('#retraction_enable').val(),
        	"retraction_min_travel": $('#retraction_min_travel').val(),
        	"retraction_combing": $('#retraction_combing').val(),
        	"retraction_minimal_extrusion": $('#retraction_minimal_extrusion').val(),
        	"retraction_hop": $('#retraction_hop').val(),
        	"retraction_speed": $('#retraction_speed').val(),
        	"retraction_amount": $('#retraction_amount').val(),
        	
        	"solid_layer_thickness": $('#solid_layer_thickness').val(),
        	"fill_density": $('#fill_density').val(),
        	"solid_top": $('#solid_top').val(),
        	"solid_bottom": $('#solid_bottom').val(),
        	"fill_overlap": $('#fill_overlap').val(),
        	
        	"print_speed": $('#print_speed').val(),
        	"print_temperature": $('#print_temperature').val(),
        	"print_temperature2": $('#print_temperature2').val(),
        	"print_bed_temperature": $('#print_bed_temperature').val(),
        	"travel_speed": $('#travel_speed').val(),
        	"bottom_layer_speed": $('#bottom_layer_speed').val(),
        	"infill_speed": $('#infill_speed').val(),
        	"solidarea_speed": $('#solidarea_speed').val(),
        	"inset0_speed": $('#inset0_speed').val(),
        	"insetx_speed": $('#insetx_speed').val(),
        	
        	"support": $('#support').val(),
        	"support_type": $('#support_type').val(),
        	"support_angle": $('#support_angle').val(),
        	"support_fill_rate": $('#support_fill_rate').val(),
        	"support_xy_distance": $('#support_xy_distance').val(),
        	"support_z_distance": $('#support_z_distance').val(),
        	"platform_adhesion": $('#platform_adhesion').val(),
        	"skirt_line_count": $('#skirt_line_count').val(),
        	"skirt_gap": $('#skirt_gap').val(),
        	"skirt_minimal_length": $('#skirt_minimal_length').val(),
        	"brim_line_count": $('#brim_line_count').val(),
        	"raft_margin": $('#raft_margin').val(),
        	"raft_line_spacing": $('#raft_line_spacing').val(),
        	"raft_base_thickness": $('#raft_base_thickness').val(),
        	"raft_base_linewidth": $('#raft_base_linewidth').val(),
        	"raft_interface_thickness": $('#raft_interface_thickness').val(),
        	"raft_interface_linewidth": $('#raft_interface_linewidth').val(),
        	"raft_airgap_all": $('#raft_airgap_all').val(),
        	"raft_airgap": $('#raft_airgap').val(),
        	"raft_surface_layers": $('#raft_surface_layers').val(),
        	"raft_surface_thickness": $('#raft_surface_thickness').val(),
        	"raft_surface_linewidth": $('#raft_surface_linewidth').val(),

        	"cool_min_layer_time": $('#cool_min_layer_time').val(),
        	"fan_enabled": $('#fan_enabled').val(),
        	"fan_full_height": $('#fan_full_height').val(),
        	"fan_speed": $('#fan_speed').val(),
        	"fan_speed_max": $('#fan_speed_max').val(),
        	"cool_min_feedrate": $('#cool_min_feedrate').val(),
        	"cool_head_lift": $('#cool_head_lift').val(),
	    },
	    "machine_type_name": "Default",
	    "add_machine_data": {
	    	"machine_name": "Default",
	        "box_name": $('#box_name').val(),
	        "machine_type": $('#machine_type').val(),
	        "machine_width": $('#machine_width').val(),
	        "machine_depth": $('#machine_depth').val(),
	        "machine_height": $('#machine_height').val(),
	        "machine_center_is_zero": $('#machine_center_is_zero').val(),
	        "has_heated_bed": $('#has_heated_bed').val(),
	        "machine_shape": $('#machine_shape').val(),
	        "extruder_amount": $('#extruder_amount').val(),
	        "extruder_offset_x2": $('#extruder_offset_x2').val(),
	        "extruder_offset_y2": $('#extruder_offset_y2').val(),
	        "serial_port": $('#serial_port').val(),
	        "serial_baud": $('#serial_baud').val(),
	        "extruder_head_size_min_x": $('#extruder_head_size_min_x').val(),
	        "extruder_head_size_min_y": $('#extruder_head_size_min_y').val(),
	        "extruder_head_size_max_x": $('#extruder_head_size_max_x').val(),
	        "extruder_head_size_max_y": $('#extruder_head_size_max_y').val(),
	        "extruder_head_size_height": $('#extruder_head_size_height').val()
	    },
	    "machine_type_changed": machine_type_changed
	};

	hidden_all();
	show_prepare("打印设置", "设定中...");
	jQuery.ajax({
        url: "settings/machines/edit",
        type: "POST",
        contentType: "application/json; charset=UTF-8",
        dataType: "json",
        data: JSON.stringify(request_data),
        success: function(response) {
			show_response(response);
        }
    });
	}
 
 function extruder_amount_change() {
	var select = $('#extruder_amount').val();
	if (select == "1") {
		$('#extruder2_display').css("display","none");
		$('#filament_diameter2_display').css("display","none");
		$('#print_temperature2_display').css("display","none");
	}
	else if(select == "2") {
		$('#extruder2_display').css("display","");
		$('#filament_diameter2_display').css("display","");
		$('#print_temperature2_display').css("display","");
	}
	else {
		
	}
}
 
 $(function(){
	$(document).on('keydown','.setParameters input[type="text"]',function(){
		if($(this).val()==0){
			//alert(1)
		}
	})
	
	
	if($('#ipSd').is(':checked')){
		$(".wired .subItem").find('input:text').removeAttr('disabled');
	}
})
