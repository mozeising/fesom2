# Patrick, Scholz 26.04.2018
import numpy as np
import time
import os
from netCDF4 import Dataset
import matplotlib.pyplot as plt
import matplotlib.patches as Polygon
from colormap_c2c    import *

#+___CALCULATE MERIDIONAL OVERTURNING FROM VERTICAL VELOCITIES________________________________________+
#| Global MOC, Atlantik MOC, Indo-Pacific MOC, Indo MOC                                               |
#|                                                                                                    |
#+____________________________________________________________________________________________________+
def calc_xmoc(mesh,data,dlat=1.0,do_onelem=True,do_output=True,which_moc='gmoc',in_elemidx=[], out_elemidx=False):
    
    #_________________________________________________________________________________________________
    t1=time.time()
    if do_output==True: print('     --> calculate '+which_moc.upper()+' from vertical velocities via meridional bins')
        
    #_________________________________________________________________________________________________
    # calculate/use index for basin domain limitation
    if which_moc=='gmoc':
        in_elemidx=[]
    else:    
        if len(in_elemidx)==0:
            if which_moc=='amoc':
                box_moc = [-100.0,36.0,-30.0,79.0]
                in_elemidx=calc_basindomain(mesh,box_moc)
            if which_moc=='amoc2':
                box_moc = [[-100.0,36.0,-30.0,79.0],[-180.0,180.0,65.0,90.0]]
                in_elemidx=calc_basindomain(mesh,box_moc)    
            elif which_moc=='pmoc':
                box_moc = [[30.0,180.0,-30.0,65.0],[-180.0,-65.0,-30.0,65.0]]
                in_elemidx=calc_basindomain(mesh,box_moc)    
            elif which_moc=='imoc':
                box_moc = [48.0,77.0,9.0,32.0]
                in_elemidx=calc_basindomain(mesh,box_moc)    

            #fig = plt.figure(figsize=[10,5])
            #plt.triplot(mesh.nodes_2d_xg,mesh.nodes_2d_yg,mesh.elem_2d_i[in_elemidx,:],linewidth=0.2)
            #plt.axis('scaled')
            #plt.title('Basin limited domain')
            #plt.show()
        
    #_________________________________________________________________________________________________
    # do moc calculation either on nodes or on elements. In moment local moc calculation is just 
    # supported on elements
    if do_onelem==True:
        
        # ncfile  = Dataset(os.path.join(data.path, data.runid+'.mesh.diag.nc'))
        # elem0_2d_iz=ncfile.variables['nlevels'][:]-1
        # mat_2d_iz = np.concatenate((elem0_2d_iz,elem0_2d_iz[mesh.pbndtri_2d_i]))
        mat_2d_iz = np.concatenate(( mesh.elem0_2d_iz,mesh.elem0_2d_iz[mesh.pbndtri_2d_i]))-1
    
        # calc triangle area if not alredy exist
        if len(mesh.elem_2d_area)==0: mesh.fesom_calc_triarea()
        mat_2d_area = mesh.elem_2d_area*1e6
        
        # mean over elements
        mat_mean = data.value[mesh.elem_2d_i,:].sum(axis=1)/3.0*1e-6
        
        if len(in_elemidx)>0:
            mat_mean = mat_mean[in_elemidx]
            # create meridional bins
            triy = mesh.nodes_2d_yg[mesh.elem_2d_i[in_elemidx,:]]
            lat   = np.arange(np.floor(triy.min())+dlat/2, np.ceil(triy.max()), dlat)
            lat_i = (( mesh.nodes_2d_yg[mesh.elem_2d_i[in_elemidx,:]].sum(axis=1)/3.0-lat[0])/dlat).astype('int')
            mat_2d_area = mat_2d_area[in_elemidx]
            mat_2d_iz   = mat_2d_iz[in_elemidx]
            
        else:
            # binning latitudes
            triy = mesh.nodes_2d_yg[mesh.elem_2d_i]
            lat   = np.arange(np.floor(triy.min())+dlat/2, np.ceil(triy.max()), dlat)
            lat_i = (( mesh.nodes_2d_yg[mesh.elem_2d_i].sum(axis=1)/3.0-lat[0])/dlat).astype('int')
        del triy
     
        # calculate area weighted mean
        mat_mean = np.multiply(mat_mean, mat_2d_area[:,np.newaxis])
        del mat_2d_area
    else:
        mat_2d_iz = mesh.nodes_2d_iz-1
        
        # keep in mind that node area info is changing over depth--> therefor load from file 
        ncfile  = Dataset(os.path.join(data.path, data.runid+'.mesh.diag.nc'))
        mat_2d_area=ncfile.variables['nod_area'][:,:].transpose()
        mat_2d_area = np.concatenate((mat_2d_area,mat_2d_area[mesh.pbndn_2d_i,:]),axis=0)
        
        # create meridional bins
        lat   = np.arange(-90+dlat/2, 90-dlat/2, dlat)
        lat_i = (( mesh.nodes_2d_yg-lat[0])/dlat).astype('int')
        
        # mean over elements
        mat_mean = data.value*1e-6
        
        # calculate area weighted mean
        mat_mean = np.multiply(mat_mean, mat_2d_area)
        del mat_2d_area
        
    #_________________________________________________________________________________________________
    # This approach is five time faster than the original from dima at least for COREv2 mesh but
    # needs probaply a bit more RAM
    moc     = np.zeros([mesh.nlev,lat.size])
    bottom  = np.zeros([lat.size,])
    numbtri = np.zeros([lat.size,])
    topo    = np.float32(mesh.zlev[mat_2d_iz+1])
    
    # this is more or less requird so bottom patch looks aceptable
    if which_moc=='pmoc':
        topo[np.where(topo>-30.0)[0]]=np.nan  
    else:
        #topo[np.where(topo>-100.0)[0]]=np.nan  
        topo[np.where(topo>-30.0)[0]]=np.nan  
    
    # be sure ocean floor is setted to zero
    for di in range(0,mesh.nlev):
        mat_idx = np.where(di>mat_2d_iz-1)[0]
        mat_mean[mat_idx,di]=0.0
        
    # loop over meridional bins
    for bini in range(lat_i.min(), lat_i.max()+1):
        numbtri[bini]= np.sum(lat_i==bini)
        #print(numbtri[bini])
        moc[:, bini]=mat_mean[lat_i==bini,:].sum(axis=0)
        #bottom[bini] = np.nanmedian(topo[lat_i==bini])
        bottom[bini] = np.nanpercentile(topo[lat_i==bini],25)
        
    # kickout outer bins where eventually no triangles are found
    idx    = numbtri>0
    moc    = moc[:,idx]
    bottom = bottom[idx]
    lat    = lat[idx]
    
    # do cumulative summation to finally calculate moc
    if len(in_elemidx)>0:
        moc = np.fliplr(moc)
        moc = -moc.cumsum(axis=1)
        moc = np.fliplr(moc)
    else:
        moc = moc.cumsum(axis=1)
    
    #_________________________________________________________________________________________________
    # smooth bottom line a bit 
    #filt=np.array([1,2,3,2,1])
    filt=np.array([1,2,1])
    filt=filt/np.sum(filt)
    aux = np.concatenate( (np.ones((filt.size,))*bottom[0],bottom,np.ones((filt.size,))*bottom[-1] ) )
    aux = np.convolve(aux,filt,mode='same')
    bottom = aux[filt.size:-filt.size]
    
    #_________________________________________________________________________________________________
    t2=time.time()
    if do_output==True: print('         elpased time:'+str(t2-t1)+'s')
        
    #_________________________________________________________________________________________________
    # variable number of output fields if you also want to write out the basin limited domain index
    #if out_elemidx==True and which_moc!='gmoc':    
    if out_elemidx==True:       
        return(moc,lat,bottom,in_elemidx)
    else:
        return(moc,lat,bottom)
    
 
#+___PLOT MERIDIONAL OVERTRUNING CIRCULATION  ________________________________________________________+
#|                                                                                                    |
#+____________________________________________________________________________________________________+
def plot_xmoc(lat,depth,moc,bottom=[],which_moc='gmoc',str_descript='',str_time='',figsize=[]):    
    
    if len(figsize)==0: figsize=[14,6]
    fig= plt.figure(figsize=figsize)
    
    resolution = 'c'
    fsize = 10
    txtx, txty = lat[0]+5,depth[-1]+100
    
    #+_________________________________________________________________________+
    #| set minimum, maximum and reference values for the creation of the       |
    #| adjustable colormap                                                     |
    #+_________________________________________________________________________+
    cnumb = 20; # minimum number of colors
    #cmin,cmax,cref  = -6,16,0 # [cmin, cmax, cref]  --> MLD2
    cmin,cmax,cref  = moc[np.where(depth<=-500)[0][0]::,:].min(),moc[np.where(depth<=-500)[0][0]::,:].max(),0 # [cmin, cmax, cref]  --> MLD2
    cmap0,clevel = colormap_c2c(cmin,cmax,cref,cnumb,'blue2red')
    cbot = [0.5,0.5,0.5]
    do_drawedges=True
    if clevel.size>30: do_drawedges=False

    #+_________________________________________________________________________+
    #| plot AXES1                                                              |
    #+_________________________________________________________________________+
    ax1 = plt.gca()    
    data_plot = moc
    data_plot[data_plot<clevel[ 0]]  = clevel[ 0]+np.finfo(np.float32).eps
    data_plot[data_plot>clevel[-1]] = clevel[-1]-np.finfo(np.float32).eps
    hp1=plt.contourf(lat,depth,data_plot,levels=clevel,extend='both',cmap=cmap0)
    plt.contour(lat,depth,data_plot,levels=clevel,colors='k',linewidths=[0.5,0.25],antialised=True)
    if len(bottom)>0:
        ax1.plot(lat,bottom,color='k')
        ax1.fill_between(lat, bottom, depth[-1],color=cbot,zorder=2)#,alpha=0.95)

    #_______________________________________________________________________________
    for im in ax1.get_images():
        im.set_clim(clevel[0],clevel[-1])
    #_______________________________________________________________________________    
    ax1.text(txtx,txty,str_descript , fontsize=14, fontweight='bold',horizontalalignment='left')
    ax1.grid(color='k', linestyle='-', linewidth=0.25,alpha=1.0)
    ax1.set_xlabel('Latitudes [deg]',fontsize=12)
    ax1.set_ylabel('Depth [m]',fontsize=12)
    
    #+_________________________________________________________________________+
    #| plot first colorbar                                                     |
    #+_________________________________________________________________________+
    cbar1 = plt.colorbar(hp1,ax=ax1,ticks=clevel,drawedges=True,extend='neither',extendrect=False,extendfrac='auto')
    cbar1.set_label('Global Meridional Overturning Circulation [Sv]'+'\n'+str_time, size=fsize+2)
    if which_moc=='gmoc':
        cbar1.set_label('Global Meridional Overturning Circulation [Sv]'+'\n'+str_time, size=fsize+2)
    elif which_moc=='amoc' or which_moc=='amoc2':
        cbar1.set_label('Atlantic Meridional Overturning Circulation [Sv]'+'\n'+str_time, size=fsize+2)
    elif which_moc=='pmoc':
        cbar1.set_label('Indo-Pacific Meridional Overturning Circulation [Sv]'+'\n'+str_time, size=fsize+2)
    elif which_moc=='imoc':
        cbar1.set_label('Indo Meridional Overturning Circulation [Sv]'+'\n'+str_time, size=fsize+2)

    ncbar_l=len(cbar1.ax.get_yticklabels()[:])
    idx_cref = np.where(clevel==cref)[0]
    idx_cref = np.asscalar(idx_cref)
    nmax_cbar_l = 10
    nstep = ncbar_l/nmax_cbar_l
    nstep = np.int(np.floor(nstep))
    if nstep==0: nstep=1
    plt.setp(cbar1.ax.get_yticklabels()[:], visible=False)
    plt.setp(cbar1.ax.get_yticklabels()[idx_cref::nstep], visible=True)
    plt.setp(cbar1.ax.get_yticklabels()[idx_cref::-nstep], visible=True)
    plt.show(block=False)    
    
    return(fig,ax1)
    
    
#+___CALCULATE BASIN LIMITED DOMAIN___________________________________________________________________+
#| to calculate the regional moc (amoc,pmoc,imoc) the domain needs be limited to corresponding basin.
#| here the elemental index of the triangels in the closed basin is calcualted
#+____________________________________________________________________________________________________+
def calc_basindomain(mesh,box_moc,do_output=False):
    
    if do_output==True: print('     --> calculate regional basin limited domain')
    box_moc = np.matrix(box_moc)
    for bi in range(0,box_moc.shape[0]):
        #_____________________________________________________________________________________________
        box_idx = mesh.nodes_2d_xg[mesh.elem_2d_i].sum(axis=1)/3.0<box_moc[bi,0]
        box_idx = np.logical_or(box_idx,mesh.nodes_2d_xg[mesh.elem_2d_i].sum(axis=1)/3.0>box_moc[bi,1])
        box_idx = np.logical_or(box_idx,mesh.nodes_2d_yg[mesh.elem_2d_i].sum(axis=1)/3.0<box_moc[bi,2])
        box_idx = np.logical_or(box_idx,mesh.nodes_2d_yg[mesh.elem_2d_i].sum(axis=1)/3.0>box_moc[bi,3])
        box_idx = np.where(box_idx==False)[0]
        box_elem2di = mesh.elem_2d_i[box_idx,:]

        #_____________________________________________________________________________________________
        # calculate edge indices of box limited domain
        edge_12     = np.sort(np.array(box_elem2di[:,[0,1]]),axis=1)
        edge_23     = np.sort(np.array(box_elem2di[:,[1,2]]),axis=1)
        edge_31     = np.sort(np.array(box_elem2di[:,[2,0]]),axis=1)
        edge_triidx = np.arange(0,box_elem2di.shape[0],1)

        #_____________________________________________________________________________________________
        # start with seed triangle
        seed_pts     = [box_moc[bi,0]+(box_moc[bi,1]-box_moc[bi,0])/2.0,box_moc[bi,2]+(box_moc[bi,3]-box_moc[bi,2])/2.0]
        seed_triidx  = np.argsort((mesh.nodes_2d_xg[box_elem2di].sum(axis=1)/3.0-seed_pts[0])**2 + (mesh.nodes_2d_yg[box_elem2di].sum(axis=1)/3.0-seed_pts[1])**2,axis=-0)[0]
        seed_elem2di = box_elem2di[seed_triidx,:]
        seed_edge    = np.concatenate((seed_elem2di[:,[0,1]], seed_elem2di[:,[1,2]], seed_elem2di[:,[2,0]]),axis=0)     
        seed_edge    = np.sort(seed_edge,axis=1) 
        
        # already delete seed triangle and coresbonding edges from box limited domain list
        edge_triidx = np.delete(edge_triidx,seed_triidx)
        edge_12     = np.delete(edge_12,seed_triidx,0)
        edge_23     = np.delete(edge_23,seed_triidx,0)
        edge_31     = np.delete(edge_31,seed_triidx,0)

        #_____________________________________________________________________________________________
        # do iterative search of which triangles are connected to each other and form cluster
        t1 = time.time()
        tri_merge_idx = np.zeros((box_elem2di.shape[0],),dtype='int')
        tri_merge_count = 0
        for ii in range(0,10000): 
            #print(ii,tri_merge_count,seed_edge.shape[0])
        
            # determine which triangles contribute to edge
            triidx12 = ismember_rows(seed_edge,edge_12)
            triidx23 = ismember_rows(seed_edge,edge_23)
            triidx31 = ismember_rows(seed_edge,edge_31)
        
            # calculate new seed edges
            seed_edge = np.concatenate((edge_23[triidx12,:],edge_31[triidx12,:],\
                                        edge_12[triidx23,:],edge_31[triidx23,:],\
                                        edge_12[triidx31,:],edge_23[triidx31,:]))
            
            # collect all found connected triagles    
            triidx = np.concatenate((triidx12,triidx23,triidx31))
            triidx = np.unique(triidx)
            
            # break out of iteration loop 
            if triidx.size==0: break 
                
            # add found trinagles to final domain list    
            tri_merge_idx[tri_merge_count:tri_merge_count+triidx.size]=edge_triidx[triidx]
            tri_merge_count = tri_merge_count+triidx.size
            
            # delete already found trinagles and edges from list
            edge_triidx = np.delete(edge_triidx,triidx)
            edge_12     = np.delete(edge_12,triidx,0)
            edge_23     = np.delete(edge_23,triidx,0)
            edge_31     = np.delete(edge_31,triidx,0)
    
            del triidx,triidx12,triidx23,triidx31
        
        tri_merge_idx = tri_merge_idx[:tri_merge_count-1]
        t2=time.time()
        if do_output==True: print('         elpased time:'+str(t2-t1)+'s')
        
        #_____________________________________________________________________________________________
        # calculate final domain limited trinagle cluster element index
        if bi==0:
            box_idx_fin = box_idx[tri_merge_idx]
        else:
            box_idx_fin = np.concatenate((box_idx_fin,box_idx[tri_merge_idx]))
        
    return(box_idx_fin)


#+___EQUIVALENT OF MATLAB ISMEMBER FUNCTION___________________________________________________________+
#|                                                                                                    |
#+____________________________________________________________________________________________________+
def ismember_rows(a, b):
	return np.flatnonzero(np.in1d(b[:,0], a[:,0]) & np.in1d(b[:,1], a[:,1]))
	