#!/usr/bin/env python
"""
Plotting macros for XAFS data sets and fits

 Function          Description of what is plotted
 ---------------- -----------------------------------------------------
  plot_mu()        mu(E) for XAFS data group in various forms
  plot_bkg()       mu(E) and background mu0(E) for XAFS data group
  plot_chik()      chi(k) for XAFS data group
  plot_chie()      chi(E) for XAFS data group
  plot_chir()      chi(R) for XAFS data group
  plot_chifit()    chi(k) and chi(R) for fit to feffit dataset
  plot_path_k()    chi(k) for a single path of a feffit dataset
  plot_path_r()    chi(R) for a single path of a feffit dataset
  plot_paths_k()   chi(k) for model and all paths of a feffit dataset
  plot_paths_r()   chi(R) for model and all paths of a feffit dataset
 ---------------- -----------------------------------------------------
"""

from numpy import gradient, ndarray, diff, where, arange
from larch import Group, ValidateLarchPlugin
from larch.utils import (index_of, index_nearest, interp)

from larch_plugins.wx.plotter import (_getDisplay, _plot, _oplot, _newplot,
                                      _fitplot, _plot_text, _plot_marker,
                                      _plot_arrow, _plot_axvline,
                                      _plot_axhline)

LineColors = ('#1f77b4', '#d62728', '#2ca02c', '#ff7f0e', '#9467bd',
              '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf')

# common XAFS plot labels
def chirlab(kweight, show_mag=True, show_real=False, show_imag=False):
    """generate chi(R) label for a kweight

    Arguments
    ----------
     kweight      k-weight to use (required)
     show_mag     bool whether to plot |chi(R)| [True]
     show_real    bool whether to plot Re[chi(R)] [False]
     show_imag    bool whether to plot Im[chi(R)] [False]
    """
    ylab = []
    if show_mag:  ylab.append(plotlabels.chirmag)
    if show_real: ylab.append(plotlabels.chirre)
    if show_imag: ylab.append(plotlabels.chirim)
    if len(ylab) > 1:  ylab = [plotlabels.chir]
    return ylab[0].format(kweight+1)
#enddef

plotlabels = Group(k       = r'$k \rm\,(\AA^{-1})$',
                   r       = r'$R \rm\,(\AA)$',
                   energy  = r'$E\rm\,(eV)$',
                   mu      = r'$\mu(E)$',
                   norm    = r'normalized $\mu(E)$',
                   flat    = r'flattened $\mu(E)$',
                   deconv  = r'deconvolved $\mu(E)$',
                   dmude   = r'$d\mu(E)/dE$',
                   dnormde   = r'$d\mu_{\rm norm}(E)/dE$',
                   chie    = r'$\chi(E)$',
                   chikw   = r'$k^{{{0:g}}}\chi(k) \rm\,(\AA^{{-{0:g}}})$',
                   chir    = r'$\chi(R) \rm\,(\AA^{{-{0:g}}})$',
                   chirmag = r'$|\chi(R)| \rm\,(\AA^{{-{0:g}}})$',
                   chirre  = r'${{\rm Re}}[\chi(R)] \rm\,(\AA^{{-{0:g}}})$',
                   chirim  = r'${{\rm Im}}[\chi(R)] \rm\,(\AA^{{-{0:g}}})$',
                   chirpha = r'${{\rm Phase}}[\chi(R)] \rm\,(\AA^{{-{0:g}}})$',
                   e0color = '#B2B282',
                   chirlab = chirlab)

def _get_title(dgroup, title=None):
    """get best title for group"""
    if title is not None:
        return title
    #endif
    data_group = getattr(dgroup, 'data', None)

    for attr in ('title', 'plot_title', 'filename', 'name', '__name__'):
        t = getattr(dgroup, attr, None)
        if t is not None:
            return t
        #endif
        if data_group is not None:
            t = getattr(data_group, attr, None)
            if t is not None:
                return t
            #endif
        #endif
    #endfor

    return repr(dgroup)
#enddef

@ValidateLarchPlugin
def redraw(win=1, show_legend=True, stacked=False, _larch=None):
    try:
        panel = _getDisplay(win=win, stacked=stacked, _larch=_larch).panel
    except AttributeError:
        return
    #endtry
    panel.conf.show_legend = show_legend
    if show_legend:  # note: draw_legend *will* redraw the canvas
        panel.conf.draw_legend()
    else:
        panel.canvas.draw()
    #endif
#enddef

@ValidateLarchPlugin
def plot_mu(dgroup, show_norm=False, show_deriv=False,
            show_pre=False, show_post=False, show_e0=False, with_deriv=False,
            emin=None, emax=None, label='mu', new=True, delay_draw=False,
            offset=0, title=None, win=1, _larch=None):
    """
    plot_mu(dgroup, norm=False, deriv=False, show_pre=False, show_post=False,
             show_e0=False, show_deriv=False, emin=None, emax=None, label=None,
             new=True, win=1)

    Plot mu(E) for an XAFS data group in various forms

    Arguments
    ----------
     dgroup     group of XAFS data after pre_edge() results (see Note 1)
     show_norm  bool whether to show normalized data [False]
     show_deriv bool whether to show derivative of XAFS data [False]
     show_pre   bool whether to show pre-edge curve [False]
     show_post  bool whether to show post-edge curve [False]
     show_e0    bool whether to show E0 [False]
     with_deriv bool whether to show deriv together with mu [False]
     emin       min energy to show, relative to E0 [None, start of data]
     emax       max energy to show, relative to E0 [None, end of data]
     label      string for label [None:  'mu', `dmu/dE', or 'mu norm']
     title      string for plot titlel [None, may use filename if available]
     new        bool whether to start a new plot [True]
     delay_draw bool whether to delay draw until more traces are added [False]
     offset      vertical offset to use for y-array [0]
     win        integer plot window to use [1]

    Notes
    -----
     1. The input data group must have the following attributes:
         energy, mu, norm, e0, pre_edge, edge_step
    """
    if hasattr(dgroup, 'mu'):
        mu = dgroup.mu
    elif  hasattr(dgroup, 'mutrans'):
        mu = dgroup.mutrans
    elif  hasattr(dgroup, 'mufluor'):
        mu = dgroup.mufluor
    else:
        raise ValueError("XAFS data group has no array for mu")
    #endif
    ylabel = plotlabels.mu
    if label is None:
        label = 'mu'
    #endif
    if show_deriv:
        mu = gradient(mu)/gradient(dgroup.energy)
        ylabel = plotlabels.dmude
        dlabel = '%s (deriv)' % label
    elif show_norm:
        mu = dgroup.norm
        ylabel = "%s (norm)" % ylabel
        dlabel = "%s (norm)" % label
    #endif
    xmin, xmax = None, None
    if emin is not None: xmin = dgroup.e0 + emin
    if emax is not None: xmax = dgroup.e0 + emax

    title = _get_title(dgroup, title=title)

    opts = dict(win=win, show_legend=True, linewidth=3,
                title=title, xmin=xmin, xmax=xmax,
                delay_draw=True, _larch=_larch)

    _plot(dgroup.energy, mu+offset, xlabel=plotlabels.energy, ylabel=ylabel,
          label=label, zorder=20, new=new, **opts)

    if with_deriv:
        dmu = gradient(mu)/gradient(dgroup.energy)
        _plot(dgroup.energy, dmu+offset, ylabel=plotlabels.dmude,
              label='%s (deriv)' % label, zorder=18, side='right', **opts)
    #endif
    if (not show_norm and not show_deriv):
        if show_pre:
            _plot(dgroup.energy, dgroup.pre_edge+offset, label='pre_edge',
                  zorder=18, **opts)
        #endif
        if show_post:
            _plot(dgroup.energy, dgroup.post_edge+offset, label='post_edge',
                  zorder=18, **opts)
            if show_pre:
                i = index_of(dgroup.energy, dgroup.e0)
                ypre = dgroup.pre_edge[i]
                ypost = dgroup.post_edge[i]
                _plot_arrow(dgroup.e0, ypre, dgroup.e0+offset, ypost,
                            color=plotlabels.e0color, width=0.25,
                            head_width=0, zorder=3, win=win, _larch=_larch)
            #endif
        #endif
    #endif
    if show_e0:
        _plot_axvline(dgroup.e0, zorder=2, size=3,
                      label='E0', color=plotlabels.e0color, win=win,
                      _larch=_larch)
        _getDisplay(win=win, _larch=_larch).panel.conf.draw_legend()
    #endif
    redraw(win=win, _larch=_larch)
#enddef

@ValidateLarchPlugin
def plot_bkg(dgroup, norm=True, emin=None, emax=None, show_e0=False,
             label=None, title=None, new=True, delay_draw=False, offset=0,
             win=1, _larch=None):
    """
    plot_bkg(dgroup, norm=True, emin=None, emax=None, show_e0=False, label=None, new=True, win=1):

    Plot mu(E) and background mu0(E) for XAFS data group

    Arguments
    ----------
     dgroup      group of XAFS data after autobk() results (see Note 1)
     norm        bool whether to show normalized data [True]
     emin        min energy to show, relative to E0 [None, start of data]
     emax        max energy to show, relative to E0 [None, end of data]
     show_e0     bool whether to show E0 [False]
     label       string for label [``None``: 'mu']
     title       string for plot titlel [None, may use filename if available]
     new         bool whether to start a new plot [True]
     delay_draw  bool whether to delay draw until more traces are added [False]
     offset      vertical offset to use for y-array [0]
     win         integer plot window to use [1]

    Notes
    -----
     1. The input data group must have the following attributes:
         energy, mu, bkg, norm, e0, pre_edge, edge_step, filename
    """
    if hasattr(dgroup, 'mu'):
        mu = dgroup.mu
    elif  hasattr(dgroup, 'mutrans'):
        mu = dgroup.mutrans
    else:
        raise ValueError("XAFS data group has no array for mu")
    #endif

    bkg = dgroup.bkg
    ylabel = plotlabels.mu
    if label is None:
        label = 'mu'
    #endif
    xmin, xmax = None, None
    if emin is not None: xmin = dgroup.e0 + emin
    if emax is not None: xmax = dgroup.e0 + emax
    if norm:
        mu  = dgroup.norm
        bkg = (dgroup.bkg - dgroup.pre_edge) / dgroup.edge_step
        ylabel = "%s (norm)" % ylabel
        label = "%s (norm)" % label
    #endif
    title = _get_title(dgroup, title=title)

    opts = dict(win=win, show_legend=True, linewidth=3,
                delay_draw=True, _larch=_larch)
    _plot(dgroup.energy, mu+offset, xlabel=plotlabels.energy, ylabel=ylabel,
         title=title, label=label, zorder=20, new=new, xmin=xmin, xmax=xmax,
         **opts)
    _plot(dgroup.energy, bkg+offset, zorder=18, label='bkg', **opts)
    if show_e0:
        _plot_axvline(dgroup.e0, zorder=2, size=3, label='E0',
                      color=plotlabels.e0color, win=win, _larch=_larch)
        _getDisplay(win=win, _larch=_larch).panel.conf.draw_legend()
    #endif
    redraw(win=win, _larch=_larch)
#enddef

@ValidateLarchPlugin
def plot_chie(dgroup, emin=-25, emax=None, label=None, title=None,
              new=True, delay_draw=False, offset=0, win=1, _larch=None):
    """
    plot_chie(dgroup, emin=None, emax=None, label=None, new=True, win=1):

    Plot chi(E) for XAFS data group

    Arguments
    ----------
     dgroup      group of XAFS data after autobk() results (see Note 1)
     emin        min energy to show, relative to E0 [-25]
     emax        max energy to show, relative to E0 [None, end of data]
     label       string for label [``None``: 'mu']
     title       string for plot titlel [None, may use filename if available]
     new         bool whether to start a new plot [True]
     delay_draw  bool whether to delay draw until more traces are added [False]
     offset      vertical offset to use for y-array [0]
     win         integer plot window to use [1]

    Notes
    -----
     1. The input data group must have the following attributes:
         energy, mu, bkg, norm, e0, pre_edge, edge_step, filename
    """
    if hasattr(dgroup, 'mu'):
        mu = dgroup.mu
    elif  hasattr(dgroup, 'mutrans'):
        mu = dgroup.mutrans
    else:
        raise ValueError("XAFS data group has no array for mu")
    #endif

    chie = mu - dgroup.bkg
    xmin, xmax = dgroup.e0-25.0, None
    if emin is not None:
        xmin = dgroup.e0 + emin
    if emax is not None:
        xmax = dgroup.e0 + emax

    title = _get_title(dgroup, title=title)

    _plot(dgroup.energy, chie+offset, xlabel=plotlabels.energy,
          ylabel=plotlabels.chie, title=title, label=label, zorder=20,
          new=new, xmin=xmin, xmax=xmax, win=win, show_legend=True,
          delay_draw=delay_draw, linewidth=3, _larch=_larch)

#enddef

@ValidateLarchPlugin
def plot_chik(dgroup, kweight=None, kmax=None, show_window=True,
              scale_window=True, label=None, title=None, new=True,
              delay_draw=False, offset=0, win=1, _larch=None):
    """
    plot_chik(dgroup, kweight=None, kmax=None, show_window=True, label=None,
              new=True, win=1)

    Plot k-weighted chi(k) for XAFS data group

    Arguments
    ----------
     dgroup       group of XAFS data after autobk() results (see Note 1)
     kweight      k-weighting for plot [read from last xftf(), or 0]
     kmax         max k to show [None, end of data]
     show_window  bool whether to also plot k-window [True]
     scale_window bool whether to scale k-window to max |chi(k)| [True]
     label        string for label [``None`` to use 'chi']
     title        string for plot titlel [None, may use filename if available]
     new          bool whether to start a new plot [True]
     delay_draw   bool whether to delay draw until more traces are added [False]
     offset       vertical offset to use for y-array [0]
     win          integer plot window to use [1]

    Notes
    -----
     1. The input data group must have the following attributes:
         k, chi, kwin, filename
    """
    if kweight is None:
        kweight = 0
        xft = getattr(dgroup, 'xftf_details', None)
        if xft is not None:
            kweight = xft.call_args.get('kweight', 0)
        #endif
    #endif

    chi = dgroup.chi * dgroup.k ** kweight
    opts = dict(win=win, show_legend=True, delay_draw=True, linewidth=3,
                _larch=_larch)
    if label is None:
        label = 'chi'
    #endif
    title = _get_title(dgroup, title=title)
    _plot(dgroup.k, chi+offset, xlabel=plotlabels.k,
         ylabel=plotlabels.chikw.format(kweight), title=title,
         label=label, zorder=20, new=new, xmax=kmax, **opts)

    if show_window and hasattr(dgroup, 'kwin'):
        kwin = dgroup.kwin
        if scale_window:
            kwin = kwin*max(abs(chi))
        _plot(dgroup.k, kwin+offset, zorder=12, label='window',  **opts)
    #endif
    redraw(win=win, _larch=_larch)
#enddef


@ValidateLarchPlugin
def plot_chir(dgroup, show_mag=True, show_real=False, show_imag=False,
              rmax=None, label=None, title=None, new=True, delay_draw=False,
              offset=0, win=1, _larch=None):
    """
    plot_chir(dgroup, show_mag=True, show_real=False, show_imag=False,
              rmax=None, label=None, new=True, win=1)

    Plot chi(R) for XAFS data group

    Arguments
    ----------
     dgroup       group of XAFS data after xftf() results (see Note 1)
     show_mag     bool whether to plot |chi(R)| [True]
     show_real    bool whether to plot Re[chi(R)] [False]
     show_imag    bool whether to plot Im[chi(R)] [False]
     label        string for label [``None`` to use 'chir']
     title        string for plot titlel [None, may use filename if available]
     rmax         max R to show [None, end of data]
     new          bool whether to start a new plot [True]
     delay_draw   bool whether to delay draw until more traces are added [False]
     offset       vertical offset to use for y-array [0]
     win          integer plot window to use [1]

    Notes
    -----
     1. The input data group must have the following attributes:
         r, chir_mag, chir_im, chir_re, kweight, filename
    """

    kweight = dgroup.xftf_details.call_args['kweight']
    title = _get_title(dgroup, title=title)

    opts = dict(win=win, show_legend=True, linewidth=3, title=title,
                zorder=20, xmax=rmax, xlabel=plotlabels.r, new=new,
                delay_draw=True, _larch=_larch)

    ylabel = plotlabels.chirlab(kweight, show_mag=show_mag,
                                show_real=show_real, show_imag=show_imag)
    opts['ylabel'] = ylabel

    if label is None:
        label = 'chir'
    #endif
    if show_mag:
        _plot(dgroup.r, dgroup.chir_mag+offset, label='%s (mag)' % label, **opts)
        opts['new'] = False
    #endif
    if show_real:
        _plot(dgroup.r, dgroup.chir_re+offset, label='%s (real)' % label, **opts)
        opts['new'] = False
    #endif
    if show_imag:
        _plot(dgroup.r, dgroup.chir_im+offset, label='%s (imag)' % label, **opts)
    #endif
    redraw(win=win, _larch=_larch)
#enddef

@ValidateLarchPlugin
def plot_chifit(dataset, kmin=0, kmax=None, kweight=None, rmax=None,
                show_mag=True, show_real=False, show_imag=False,
                title=None, new=True, delay_draw=False, offset=0, win=1,
                _larch=None):
    """
    plot_chifit(dataset, kmin=0, kmax=None, rmax=None,
                show_mag=True, show_real=False, show_imag=False,
                new=True, win=1)

    Plot k-weighted chi(k) and chi(R) for fit to feffit dataset

    Arguments
    ----------
     dataset      feffit dataset, after running feffit()
     kmin         min k to show [0]
     kmax         max k to show [None, end of data]
     kweight      kweight to show [None, taken from dataset]
     rmax         max R to show [None, end of data]
     show_mag     bool whether to plot |chidr(R)| [True]
     show_real    bool whether to plot Re[chi(R)] [False]
     show_imag    bool whether to plot Im[chi(R)] [False]
     title        string for plot titlel [None, may use filename if available]
     new          bool whether to start a new plot [True]
     delay_draw   bool whether to delay draw until more traces are added [False]
     offset       vertical offset to use for y-array [0]
     win          integer plot window to use [1]

    """
    if kweight is None:
        kweight = dataset.transform.kweight
    #endif
    if isinstance(kweight, (list, tuple, ndarray)): kweight=kweight[0]

    data_chik  = dataset.data.chi * dataset.data.k**kweight
    model_chik = dataset.model.chi * dataset.model.k**kweight

    title = _get_title(dataset, title=title)

    opts=dict(labelfontsize=10, legendfontsize=10, linewidth=3,
              show_legend=True, delay_draw=True, win=win, title=title,
              _larch=_larch)

    # k-weighted chi(k) in first plot window
    _plot(dataset.data.k, data_chik+offset, xmin=kmin, xmax=kmax,
            xlabel=plotlabels.k, ylabel=plotlabels.chikw.format(kweight),
            label='data', new=new, **opts)
    _plot(dataset.model.k, model_chik+offset, label='fit',  **opts)
    redraw(win=win, _larch=_larch)
    # show chi(R) in next plot window
    opts['win'] = win = win+1

    ylabel = plotlabels.chirlab(kweight, show_mag=show_mag,
                                show_real=show_real, show_imag=show_imag)
    opts.update(dict(xlabel=plotlabels.r, ylabel=ylabel,
                     xmax=rmax, new=True, show_legend=True))

    if show_mag:
        _plot(dataset.data.r,  dataset.data.chir_mag+offset,
             label='|data|', **opts)
        opts['new'] = False
        _plot(dataset.model.r, dataset.model.chir_mag+offset,
             label='|fit|', **opts)
    #endif
    if show_real:
        _plot(dataset.data.r, dataset.data.chir_re+offset, label='Re[data]', **opts)
        opts['new'] = False
        _plot(dataset.model.r, dataset.model.chir_re+offset, label='Re[fit]',  **opts)
    #endif
    if show_imag:
        plot(dataset.data.r, dataset.data.chir_im+offset, label='Im[data]', **opts)
        opts['new'] = False
        plot(dataset.model.r, dataset.model.chir_im+offset, label='Im[fit]',  **opts)
    #endif
    redraw(win=win, _larch=_larch)
#enddef

@ValidateLarchPlugin
def plot_path_k(dataset, ipath=0, kmin=0, kmax=None, offset=0, label=None,
                new=False, delay_draw=False, win=1, _larch=None, **kws):
    """
    plot_path_k(dataset, ipath, kmin=0, kmax=None, offset=0,
               label=None, new=False, win=1, **kws)

    Plot k-weighted chi(k) for a single Path of a feffit dataset

    Arguments
    ----------
     dataset      feffit dataset, after running feffit()
     ipath        index of path, starting count at 0 [0]
     kmin         min k to show [0]
     kmax         max k to show [None, end of data]
     offset       vertical offset to use for plot [0]
     label        path label ['path %d' % ipath]
     new          bool whether to start a new plot [True]
     delay_draw   bool whether to delay draw until more traces are added [False]
     win          integer plot window to use [1]
     kws          additional keyword arguments are passed to plot()
    """
    kweight = dataset.transform.kweight
    path = dataset.pathlist[ipath]
    if label is None: label = 'path %i' % (1+ipath)

    chi_kw = offset + path.chi * path.k**kweight

    _plot(path.k, chi_kw, label=label, xmin=kmin, xmax=kmax,
         xlabel=plotlabels.k, ylabel=plotlabels.chikw.format(kweight),
         win=win, new=new, delay_draw=delay_draw, _larch=_larch, **kws)
#enddef

@ValidateLarchPlugin
def plot_path_r(dataset, ipath, rmax=None, offset=0, label=None,
                show_mag=True, show_real=False, show_imag=True,
                new=False, delay_draw=False, win=1, _larch=None,
                **kws):
    """
    plot_path_r(dataset, ipath,rmax=None, offset=0, label=None,
                show_mag=True, show_real=False, show_imag=True,
                new=False, win=1, **kws)

    Plot chi(R) for a single Path of a feffit dataset

    Arguments
    ----------
     dataset      feffit dataset, after running feffit()
     ipath        index of path, starting count at 0 [0]
     kmax         max k to show [None, end of data]
     offset       vertical offset to use for plot [0]
     label        path label ['path %d' % ipath]
     show_mag     bool whether to plot |chi(R)| [True]
     show_real    bool whether to plot Re[chi(R)] [False]
     show_imag    bool whether to plot Im[chi(R)] [False]
     new          bool whether to start a new plot [True]
     delay_draw   bool whether to delay draw until more traces are added [False]
     win          integer plot window to use [1]
     kws          additional keyword arguments are passed to plot()
    """
    path = dataset.pathlist[ipath]
    if label is None:
        label = 'path %i' % (1+ipath)
    #endif
    kweight =dataset.transform.kweight
    ylabel = plotlabels.chirlab(kweight, show_mag=show_mag,
                                show_real=show_real, show_imag=show_imag)

    opts = dict(xlabel=plotlabels.r, ylabel=ylabel, xmax=rmax, new=new,
                delay_draw=True, _larch=_larch)

    opts.update(kws)
    if show_mag:
        _plot(path.r,  offset+path.chir_mag, label=label, **opts)
        opts['new'] = False
    #endif
    if show_real:
        _plot(path.r,  offset+path.chir_re, label=label, **opts)
        opts['new'] = False
    #endif
    if show_imag:
        _plot(path.r,  offset+path.chir_im, label=label, **opts)
        opts['new'] = False
    #endif
    redraw(win=win, _larch=_larch)
#enddef

@ValidateLarchPlugin
def plot_paths_k(dataset, offset=-1, kmin=0, kmax=None, title=None,
                 new=True, delay_draw=False, win=1, _larch=None, **kws):

    """
    plot_paths_k(dataset, offset=-1, kmin=0, kmax=None, new=True, win=1, **kws):

    Plot k-weighted chi(k) for model and all paths of a feffit dataset

    Arguments
    ----------
     dataset      feffit dataset, after running feffit()
     kmin         min k to show [0]
     kmax         max k to show [None, end of data]
     offset       vertical offset to use for paths for plot [-1]
     new          bool whether to start a new plot [True]
     title        string for plot titlel [None, may use filename if available]
     win          integer plot window to use [1]
     delay_draw   bool whether to delay draw until more traces are added [False]
     kws          additional keyword arguments are passed to plot()
    """
    # make k-weighted chi(k)
    kweight = dataset.transform.kweight
    model = dataset.model

    model_chi_kw = model.chi * model.k**kweight

    title = _get_title(dataset, title=title)

    _plot(model.k, model_chi_kw, title=title, label='sum', new=new,
          xlabel=plotlabels.r, ylabel=plotlabels.chikw.format(kweight),
          xmin=kmin, xmax=kmax, win=win, delay_draw=True,_larch=_larch,
          **kws)

    for ipath in range(len(dataset.pathlist)):
        plot_path_k(dataset, ipath, offset=(ipath+1)*offset,
                    kmin=kmin, kmax=kmax, new=False, delay_draw=True,
                    win=win, _larch=_larch)
    #endfor
    redraw(win=win, _larch=_larch)
#enddef

@ValidateLarchPlugin
def plot_paths_r(dataset, offset=-0.25, rmax=None, show_mag=True,
                 show_real=False, show_imag=False, title=None, new=True,
                 win=1, delay_draw=False, _larch=None, **kws):
    """
    plot_paths_r(dataset, offset=-0.5, rmax=None, show_mag=True, show_real=False,
                 show_imag=False, new=True, win=1, **kws):

    Plot chi(R) for model and all paths of a feffit dataset

    Arguments
    ----------
     dataset      feffit dataset, after running feffit()
     offset       vertical offset to use for paths for plot [-0.5]
     rmax         max R to show [None, end of data]
     show_mag     bool whether to plot |chi(R)| [True]
     show_real    bool whether to plot Re[chi(R)] [False]
     show_imag    bool whether to plot Im[chi(R)] [False]
     title        string for plot titlel [None, may use filename if available]
     new          bool whether to start a new plot [True]
     delay_draw   bool whether to delay draw until more traces are added [False]
     win          integer plot window to use [1]
     kws          additional keyword arguments are passed to plot()
    """
    kweight = dataset.transform.kweight
    model = dataset.model

    ylabel = plotlabels.chirlab(kweight, show_mag=show_mag,
                                show_real=show_real, show_imag=show_imag)
    title = _get_title(dataset, title=title)
    opts = dict(xlabel=plotlabels.r, ylabel=ylabel, xmax=rmax, new=new,
                delay_draw=True, title=title, _larch=_larch)
    opts.update(kws)
    if show_mag:
        _plot(model.r,  model.chir_mag, label='|sum|', **opts)
        opts['new'] = False
    #endif
    if show_real:
        _plot(model.r,  model.chir_re, label='Re[sum]', **opts)
        opts['new'] = False
    #endif
    if show_imag:
        _plot(model.r,  model.chir_im, label='Im[sum]', **opts)
        opts['new'] = False
    #endif

    for ipath in range(len(dataset.pathlist)):
        plot_path_r(dataset, ipath, offset=(ipath+1)*offset,
                    show_mag=show_mag, show_real=show_real,
                    show_imag=show_imag, **opts)
    #endfor
    redraw(win=win, _larch=_larch)
#enddef


def extend_plotrange(x, y, xmin=None, xmax=None, extend=0.05):
    """return plot limits to extend a plot range for x, y pairs"""
    xeps = min(diff(x)) / 5.
    if xmin is None:
        xmin = min(x)
    if xmax is None:
        xmax = max(x)
    i0 = index_of(x, xmin + xeps)
    i1 = index_of(x, xmax + xeps) + 1

    xspan = x[i0:i1]
    xrange = max(xspan) - min(xspan)
    yspan = y[i0:i1]
    yrange = max(yspan) - min(yspan)

    return  (min(xspan) - extend * xrange,
             max(xspan) + extend * xrange,
             min(yspan) - extend * yrange,
             max(yspan) + extend * yrange)

@ValidateLarchPlugin
def plot_prepeaks_baseline(dgroup, subtract_baseline=False, show_fitrange=True,
                           show_peakrange=True, win=1, _larch=None, **kws):
    """Plot pre-edge peak baseline fit, as from `pre_edge_baseline` or XAS Viewer

    dgroup must have a 'prepeaks' attribute
    """
    if not hasattr(dgroup, 'prepeaks'):
        raise ValueError('Group needs prepeaks')
    #endif
    ppeak = dgroup.prepeaks

    px0, px1, py0, py1 = extend_plotrange(dgroup.xdat, dgroup.ydat,
                                          xmin=ppeak.emin, xmax=ppeak.emax)
    title = "pre_edge baesline\n %s" % dgroup.filename

    popts = dict(xmin=px0, xmax=px1, ymin=py0, ymax=py1, title=title,
                 xlabel='Energy (eV)', ylabel='mu', delay_draw=True,
                 show_legend=True, style='solid', linewidth=3,
                 label='data', new=True,
                 marker='None', markersize=4, win=win, _larch=_larch)
    popts.update(kws)

    ydat = dgroup.ydat
    xdat = dgroup.xdat
    if subtract_baseline:
        xdat = ppeak.energy
        ydat = ppeak.baseline
        popts['label'] = 'baseline subtracted peaks'
        _plot(xdat, ydat, **popts)
    else:
        _plot(xdat, ydat, **popts)
        popts['new'] = False
        popts['label'] = 'baseline'
        _oplot(ppeak.energy, ppeak.baseline, **popts)

    popts = dict(win=win, _larch=_larch, delay_draw=True,
                 label='_nolegend_')
    if show_fitrange:
        for x in (ppeak.emin, ppeak.emax):
            _plot_axvline(x, color='#DDDDCC', **popts)
            _plot_axvline(ppeak.centroid, color='#EECCCC', **popts)

    if show_peakrange:
        for x in (ppeak.elo, ppeak.ehi):
            y = ydat[index_of(xdat, x)]
            _plot_marker(x, y, color='#222255', marker='o', size=8, **popts)
    redraw(win=win, show_legend=True, _larch=_larch)
#enddef

@ValidateLarchPlugin
def plot_prepeaks_fit(dgroup, nfit=0, show_init=False, subtract_baseline=False,
                      show_residual=False, win=1, _larch=None):
    """plot pre-edge peak fit, as from XAS Viewer

    dgroup must have a 'peakfit_history' attribute
    """
    if not hasattr(dgroup, 'prepeaks'):
        raise ValueError('Group needs prepeaks')
    #endif
    if show_init:
        result = dgroup.prepeaks
    else:
        result = getattr(dgroup.prepeaks, 'fit_history', None)
        if nfit > len(result):
            nfit = 0
        result = result[nfit]
    #endif

    if result is None:
        raise ValueError('Group needs prepeaks.fit_history or init_fit')
    #endif

    opts = result.user_options
    xeps = min(diff(dgroup.xdat)) / 5.
    xdat = 1.0*result.energy
    ydat = 1.0*result.mu

    xdat_full = 1.0*dgroup.xdat
    ydat_full = 1.0*dgroup.ydat

    if show_init:
        yfit   = 1.0*result.init_fit
        ycomps = None
        ylabel = 'model'
    else:
        yfit   = 1.0*result.best_fit
        ycomps = result.ycomps
        ylabel = 'best fit'

    baseline = 0.*ydat
    if ycomps is not None:
        for label, ycomp in ycomps.items():
            if label in opts['bkg_components']:
                baseline += ycomp

    plotopts = dict(title='%s:\npre-edge peak' % dgroup.filename,
                    xlabel='Energy (eV)', ylabel=opts['array_desc'],
                    delay_draw=True, show_legend=True, style='solid',
                    linewidth=3, marker='None', markersize=4)

    if subtract_baseline:
        ydat -= baseline
        yfit -= baseline
        ydat_full = 1.0*ydat
        xdat_full = 1.0*xdat
        plotopts['ylabel'] = '%s-baseline' % plotopts['ylabel']

    dx0, dx1, dy0, dy1 = extend_plotrange(xdat_full, ydat_full,
                                          xmin=opts['emin'], xmax=opts['emax'])
    fx0, fx1, fy0, fy1 = extend_plotrange(xdat, yfit,
                                          xmin=opts['emin'], xmax=opts['emax'])

    plotopts.update(dict(xmin=dx0, xmax=dx1,
                         ymin=min(dy0, fy0), ymax=max(dy1, fy1)))

    ncolor = 0
    popts = {'win': win, '_larch': _larch}
    plotopts.update(popts)
    if show_residual:
        popts['stacked'] = True
        _fitplot(xdat, ydat, yfit, label='data', label2=ylabel, **plotopts)
    else:
        _plot(xdat_full, ydat_full, new=True, label='data',
              color=LineColors[0], **plotopts)
        _oplot(xdat, yfit, label=ylabel, color=LineColors[1], **plotopts)
        ncolor = 1

    if ycomps is not None:
        if not subtract_baseline:
            ncolor += 1
            _oplot(xdat, baseline, label='baseline', delay_draw=True,
                   style='short dashed', marker='None', markersize=5,
                   color=LineColors[ncolor], **popts)

        for label, ycomp in ycomps.items():
            if label in opts['bkg_components']:
                continue
            ncolor =  (ncolor+1) % 10
            _oplot(xdat, ycomp, label=label, delay_draw=True,
                   style='short dashed', marker='None', markersize=5,
                   color=LineColors[ncolor], **popts)

    if opts['show_fitrange']:
        for attr in ('emin', 'emax'):
            _plot_axvline(opts[attr], ymin=0, ymax=1,
                          delay_draw=True, color='#DDDDCC',
                          label='_nolegend_', **popts)

    if opts['show_centroid']:
        pcen = getattr(dgroup.prepeaks, 'centroid', None)
        if hasattr(result, 'params'):
            pcen = result.params.get('fit_centroid', None)
            if pcen is not None:
                pcen = pcen.value
        if pcen is not None:
            _plot_axvline(pcen, delay_draw=True, ymin=0, ymax=1,
                          color='#EECCCC', label='_nolegend_', **popts)

    redraw(show_legend=True, **popts)

@ValidateLarchPlugin
def plot_pca_components(result, max_components=None, min_weight=0,
                        win=1, _larch=None, **kws):
    """Plot components from PCA result

    result must be output of `pca_train`
    """

    if max_components is None:
        max_components = len(result.components)
    else:
        max_components = max(1, min(len(result.components), max_components))

    title = "PCA model components"

    popts = dict(xmin=result.xmin, xmax=result.xmax, title=title,
                 xlabel=plotlabels.energy, ylabel=plotlabels.norm,
                 delay_draw=True, show_legend=True, style='solid',
                 linewidth=3, new=True, marker='None', markersize=4,
                 win=win, _larch=_larch)

    popts.update(kws)

    _plot(result.x, result.mean, label='Mean', **popts)
    for i, comp in enumerate(result.components[:max_components]):
        label = 'Comp #%d' % (i+1)
        if result.variances[i] > min_weight:
            _oplot(result.x, comp, label=label, **popts)

    redraw(win=win, show_legend=True, _larch=_larch)

@ValidateLarchPlugin
def plot_pca_weights(result, max_components=None, min_weight=0,
                        win=1, _larch=None, **kws):
    """Plot component weights from PCA result

    result must be output of `pca_train`
    """
    if max_components is None:
        max_components = len(result.components)
    else:
        max_components = max(1, min(len(result.components), max_components))

    title = "PCA model weights"

    popts = dict(xmin=0, xmax=1+max_components, title=title,
                 xlabel='Component #', ylabel='weight', style='solid',
                 linewidth=1, new=True, marker='o', markersize=4, win=win,
                 _larch=_larch)

    popts.update(kws)

    nsig = len(where(result.variances > min_weight)[0])
    nsig = min(nsig, max_components)

    x = 1 + arange(nsig)
    y = result.variances[:nsig]
    _plot(x, y, label='weights', **popts)


@ValidateLarchPlugin
def plot_pca_fit(dgroup, win=1, with_components=False, _larch=None, **kws):
    """Plot data and fit result from pca_fit, which rom PCA result

    result must be output of `pca_fit`
    """

    title = "PCA model fit"
    result = dgroup.pca_result
    model = result.pca_model

    popts = dict(xmin=model.xmin, xmax=model.xmax, title=title,
                 xlabel=plotlabels.energy, ylabel=plotlabels.norm,
                 delay_draw=True, show_legend=True, style='solid',
                 linewidth=3, new=True, marker='None', markersize=4,
                 stacked=True, win=win, _larch=_larch)
    popts.update(kws)
    _fitplot(result.x, result.ydat, result.yfit,
             label='data', label2='PCA fit', **popts)

    if with_components:
        panel = _getDisplay(win=win, stacked=True, _larch=_larch).panel
        panel.oplot(result.x, model.mean, label='mean')
        for n in range(len(result.weights)):
            cval = model.components[n]*result.weights[n]
            panel.oplot(result.x, cval, label='Comp #%d' % (n+1))
    redraw(win=win, show_legend=True, stacked=True, _larch=_larch)

def initializeLarchPlugin(_larch=None):
    """initialize _xafs"""
    if _larch is None:
        return
    _larch.symtable._xafs.plotlabels  = plotlabels

def registerLarchPlugin():
    return ('_xafs', {'redraw': redraw,
                      'plot_mu':plot_mu,
                      'plot_bkg':plot_bkg,
                      'plot_chie': plot_chie,
                      'plot_chik': plot_chik,
                      'plot_chir': plot_chir,
                      'plot_chifit': plot_chifit,
                      'plot_path_k': plot_path_k,
                      'plot_path_r': plot_path_r,
                      'plot_paths_k': plot_paths_k,
                      'plot_paths_r': plot_paths_r,
                      'plot_prepeaks_fit': plot_prepeaks_fit,
                      'plot_prepeaks_baseline': plot_prepeaks_baseline,
                      'plot_pca_components': plot_pca_components,
                      'plot_pca_weights': plot_pca_weights,
                      'plot_pca_fit': plot_pca_fit,
                      })
