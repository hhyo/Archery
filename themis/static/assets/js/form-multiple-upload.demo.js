/*
Template Name: Color Admin - Responsive Admin Dashboard Template build with Twitter Bootstrap 3.3.4
Version: 1.7.0
Author: Sean Ngu
Website: http://www.seantheme.com/color-admin-v1.7/admin/
*/

var handleJqueryFileUpload = function() {
     // Initialize the jQuery File Upload widget:
    $('#fileupload').fileupload({
        autoUpload: false,
        disableImageResize: /Android(?!.*Chrome)|Opera/.test(window.navigator.userAgent),
        maxFileSize: 5000000,
        acceptFileTypes: /(\.|\/)(gif|jpe?g|png)$/i,
        // Uncomment the following to send cross-domain cookies:
        //xhrFields: {withCredentials: true},                
    });

    // Enable iframe cross-domain access via redirect option:
    $('#fileupload').fileupload(
        'option',
        'redirect',
        window.location.href.replace(
            /\/[^\/]*$/,
            '/cors/result.html?%s'
        )
    );

    // Upload server status check for browsers with CORS support:
    if ($.support.cors) {
        $.ajax({
            type: 'HEAD'
        }).fail(function () {
            $('<div class="alert alert-danger"/>').text('Upload server currently unavailable - ' + new Date()).appendTo('#fileupload');
        });
    }

    // Load & display existing files:
    $('#fileupload').addClass('fileupload-processing');
    $.ajax({
        // Uncomment the following to send cross-domain cookies:
        //xhrFields: {withCredentials: true},
        url: $('#fileupload').fileupload('option', 'url'),
        dataType: 'json',
        context: $('#fileupload')[0]
    }).always(function () {
        $(this).removeClass('fileupload-processing');
    }).done(function (result) {
        $(this).fileupload('option', 'done')
        .call(this, $.Event('done'), {result: result});
    });
};


var FormMultipleUpload = function () {
	"use strict";
    return {
        //main function
        init: function () {
            $.getScript('assets/plugins/jquery-file-upload/js/vendor/jquery.ui.widget.js').done(function() {
                $.getScript('assets/plugins/jquery-file-upload/js/vendor/tmpl.min.js').done(function() {
                    $.getScript('assets/plugins/jquery-file-upload/js/vendor/load-image.min.js').done(function() {
                        $.getScript('assets/plugins/jquery-file-upload/js/vendor/canvas-to-blob.min.js').done(function() {
                            $.getScript('assets/plugins/jquery-file-upload/blueimp-gallery/jquery.blueimp-gallery.min.js').done(function() {
                                $.getScript('assets/plugins/jquery-file-upload/js/jquery.iframe-transport.js').done(function() {
                                    $.getScript('assets/plugins/jquery-file-upload/js/jquery.fileupload.js').done(function() {
                                        $.getScript('assets/plugins/jquery-file-upload/js/jquery.fileupload-process.js').done(function() {
                                            $.getScript('assets/plugins/jquery-file-upload/js/jquery.fileupload-image.js').done(function() {
                                                $.getScript('assets/plugins/jquery-file-upload/js/jquery.fileupload-audio.js').done(function() {
                                                    $.getScript('assets/plugins/jquery-file-upload/js/jquery.fileupload-video.js').done(function() {
                                                        $.getScript('assets/plugins/jquery-file-upload/js/jquery.fileupload-validate.js').done(function() {
                                                            $.getScript('assets/plugins/jquery-file-upload/js/jquery.fileupload-ui.js').done(function() {
                                                                if ($.browser.msie && parseFloat($.browser.version) >= 8 && parseFloat($.browser.version) < 10) {
                                                                    $.getScript('assets/plugins/jquery-file-upload/js/cors/jquery.xdr-transport.js').done(function() {
                                                                        handleJqueryFileUpload();
                                                                    });
                                                                } else {
                                                                    handleJqueryFileUpload();
                                                                }
                                                            });
                                                        });
                                                    });
                                                });
                                            });
                                        });
                                    });
                                });
                            });
                        });
                    });
                });
            });
        }
    };
}();