jQuery(document).ready(function($) {
    "use strict";
    watch($('.pace-progress'), 'width', function() {
        if (this.style.width > 99 + '%') {
            Pace.stop();
        };
    });
    /* ---------------------------------------------------------------------- */
    /* ------------------ SHUFFLE JS / PUBLICATION  -------------------------- */
    /* ---------------------------------------------------------------------- */
    var $mygrid = $('#mygrid');
    $mygrid.shuffle({
        itemSelector: '.publication_item',
        speed: 500
    });
    /* reshuffle when user clicks a filter item */
    $('#filter a').on('click', function(e) {
        e.preventDefault();
        // get group name from clicked item
        var groupName = $(this).attr('data-group');
        // reshuffle grid
        $mygrid.shuffle('shuffle', groupName);
    });
    $mygrid.shuffle('shuffle', 'all');
    //sorting fonction
    $('.desc').on('click', function() {
        var sort = "date-publication",
            opts = {
                reverse: true,
                by: function($el) {
                    return $el.data('date-publication');
                }
            }

        // Filter elements
        $mygrid.shuffle('sort', opts);
    });
    $('.asc').on('click', function() {
        var sort = "date-publication",
            opts = {
                reverse: false,
                by: function($el) {
                    return $el.data('date-publication');
                }
            }

        // Filter elements
        $mygrid.shuffle('sort', opts);
    });

        /* ---------------------------------------------------------------------- */
    /* ------------------------------ MAGNIFIC POPUP ------------------------ */
    /* ---------------------------------------------------------------------- */
    $('.open_popup').magnificPopup({
        type: 'inline',
        midClick: true,
        removalDelay: 500,
        callbacks: {
            beforeOpen: function() {
                this.st.mainClass = this.st.el.attr('data-effect');
            }
        }
    });
    

});
