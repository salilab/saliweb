// extra functions needed to make FoXS gnuplot output work

gnuplot.show_plot = function(plotid) {
    if (typeof(gnuplot["hide_"+plotid]) == "unknown")
        gnuplot["hide_"+plotid] = false;
    if(gnuplot["hide_"+plotid]) gnuplot["hide_"+plotid] = false;
    ctx.clearRect(0,0,gnuplot.plot_term_xmax,gnuplot.plot_term_ymax);
    gnuplot.display_is_uptodate = false;
    gnuplot_canvas();
}

gnuplot.hide_plot = function(plotid) {
    if (typeof(gnuplot["hide_"+plotid]) == "unknown")
        gnuplot["hide_"+plotid] = false;
    if(!gnuplot["hide_"+plotid]) gnuplot["hide_"+plotid] = true;
    ctx.clearRect(0,0,gnuplot.plot_term_xmax,gnuplot.plot_term_ymax);
    gnuplot.display_is_uptodate = false;
    gnuplot_canvas();
}
