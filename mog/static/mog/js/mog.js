(function (window) {
    'use strict';

    function splitTime(time) {
        // Arguments
        // ---------
        // time: String representing a delta time.
        //       Can be D:H:M:S or H:M:S and contains
        //       zeroes to the left.
        //
        // Return
        // ------
        // Array of 4 integers [D, H, M, S]
        //
        var tokens = time.split(':');
        if (tokens.length == 3)
            tokens = [0].concat(tokens);
        if (tokens.length != 4)
            return undefined;
        tokens[0] = 1 * tokens[0];
        tokens[1] = 1 * tokens[1];
        tokens[2] = 1 * tokens[2];
        tokens[3] = 1 * tokens[3];
        return tokens;
    }

    function joinTime(tokens) {
        if (tokens[0] < 0) {
            return '00:00:00';
        }

        if (tokens[3] < 10) tokens[3] = '0' + tokens[3];
        if (tokens[2] < 10) tokens[2] = '0' + tokens[2];
        if (tokens[1] < 10) tokens[1] = '0' + tokens[1];

        if (tokens[0] == 0)
           tokens = tokens.slice(1);

        return tokens.join(':');
    }

    function timeToSeconds(time) {
        // Arguments
        // ---------
        // time: String representing a delta time.
        //       Can be D:H:M:S or H:M:S and contains
        //       zeroes to the left.
        //
        // Return
        // ------
        // Total number of seconds
        //
        var tokens = splitTime(time);
        if (tokens.length == 3) {
            return tokens[0] * 3600 + tokens[1] * 60 + tokens[2];
        } else if (tokens.length == 4) {
            return tokens[0] * 86400 + tokens[1] * 3600 + tokens[2] * 60 + tokens[3];
        }
        return undefined;
    }

    function alterSeconds(time, delta) {
        // Arguments
        // ---------
        // value: String containing a delta time (D:H:M:S or H:M:S).
        // delta: An integer used to alter seconds. Expected +1 or -1
        //        but it can be any integer.
        //
        // Return
        // ------
        // Array [D, H, M, S] with the changed time.
        //
        var tokens = splitTime(time);

        var upper = [-1, 23, 59, 59];
        for (var i = tokens.length - 1; i >= 0; i--) {
            tokens[i] += delta;
            if (tokens[i] < 0)
                tokens[i] = upper[i];
            else if (tokens[i] > upper[i])
                tokens[i] = 0;
            else break;
        }

        return joinTime(tokens);
    }

    $(document).ready(function() {
        var clocks = $('.time-update');
        if (clocks.length > 0) {
            var handler = setInterval(function() {
                var enabled = 0;

                clocks.each(function() {
                    if ($(this).data('enabled') === 'on') {
                        var delta = 1 * $(this).data('delta');
                        var oldTime = $(this).html();
                        var newTime = alterSeconds(oldTime, delta);

                        if (delta < 0 && timeToSeconds(newTime) == 0) {
                            $(this).data('enabled', 'off');
                        }

                        if (delta > 0) {
                            var upper = $(this).data('upper');
                            if (timeToSeconds(newTime) >= upper) {
                                $(this).data('enabled', 'off');
                            }
                        }

                        if (oldTime === newTime) {
                            // prevent invalid dates
                            $(this).data('enabled', 'off');
                        }

                        $(this).html(newTime);

                        if ($(this).data('enabled') === 'on')
                            enabled += 1;
                    }
                });

                if (enabled == 0)
                    clearInterval(handler);
            }, 1000);
        }
    });

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
            const $sne = $('form textarea.summernote-editor');
            $sne.each(function () {
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

        this.initializeSimpleMDE = function(isAdmin) {
            const $mde = $('form textarea.markdown-editor');
            $mde.each(function () {
                const markdownEditor = new SimpleMDE({ 
                    element: $(this)[0],
                    renderingConfig: {
                        codeSyntaxHighlighting: true,
                    },
                    shortcuts: {
                        drawTable: "Cmd-Alt-T",
                        togglePreview: "Cmd-Alt-P",
                    },
                    showIcons: [
                        "code",
                        "table",
                        "strikethrough",
                        "heading-smaller",
                        "heading-bigger",
                        "heading-1",
                        "heading-2",
                        "heading-3",
                        "clean-block",
                        "horizontal-rule",
                    ],
                    hideIcons: ["heading"],
                    previewRender: function (plainText) {
                        setTimeout(function() {
                            MathJax.Hub.Queue(
                                ["Typeset", MathJax.Hub]
                            );
                        }, 250);
                        return this.parent.markdown(plainText);
                    },
                });
            });
            const $mdv = $('.markdown-view-container textarea.markdown-view');
            $mdv.each(function () {
                const markdownEditor = new SimpleMDE({
                    element: $(this)[0],
                    shortcuts: {
                        togglePreview: null,
                    },
                    renderingConfig: {
                        codeSyntaxHighlighting: true,
                    },
                    status: false,
                    toolbar: false,
                    toolbarTips: false,
                });
                markdownEditor.togglePreview();
            });
        }
    }

    window.MOG = new MOG();
})(window);
