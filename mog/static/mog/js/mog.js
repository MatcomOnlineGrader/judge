(function (window) {
    String.prototype.format = function () {
        var formatted = this;
        for (var i = 0; i < arguments.length; i++) {
            var regexp = new RegExp('\\{' + i + '\\}', 'gi');
            formatted = formatted.replace(regexp, arguments[i]);
        }
        return formatted;
    };

    function MOG() {
        this.version = "1.0.0";

        this.initializeSummernote = function(isAdmin) {
            if (!($().summernote))
                return;
            var sns = $('form textarea');
            sns.each(function () {
                $(this).summernote({
                    height: $(this).attr('data-height') || 200,
                    lang: $(this).attr('data-lang') || 'en-US',
                    toolbar: [
                        ['style', ['style']],
                        ['fontsize', ['fontsize']],
                        ['style', ['bold', 'italic', 'underline', 'strikethrough', 'clear']],
                        ['color', ['color']],
                        ['para', ['ul', 'ol', 'paragraph']],
                        ['table', ['table']],
                        ['media', ['link', 'picture', 'video']],
                        ['misc', (isAdmin === true) ? ['codeview', 'fullscreen', 'help'] : []]
                    ]
                });
            });
        }
    }

    window.MOG = new MOG();
})(window);
