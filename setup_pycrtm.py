import os,shutil,glob,sys,argparse
import urllib.request
import tarfile
from subprocess import Popen, PIPE

def main( a ):
    
    checkInstallDirectory( a )
    fo = open('crtm.stdo','w')
    fe = open('crtm.stde','w')
    
    # remove previous source install directory
    if(len(glob.glob('REL-*'))>0): shutil.rmtree(glob.glob('REL-*')[0])
 
    arch = a.arch
    compilerFlags = selectCompilerFlags(arch)
    # set the required environment variables
    os.environ["FC"] = compilerFlags[arch]['Compiler']  
    os.environ['FCFLAGS']= compilerFlags[arch]['FCFLAGS1']
    installPath = a.install
    tarballPath = a.rtpath
    scriptDir = os.path.split(os.path.abspath(__file__))[0]
    if(a.rtinstall):
        # copy tarball from download location
        downloadExtractTar(tarballPath, scriptDir)    

        # go into extracted tarball source directory
        os.chdir( glob.glob('REL-*')[0] ) 

        print("Patching CRTM for gfortran") 
        if(arch=='gfortran-openmp'): patchCrtm(fo, fe, scriptDir)


        print("Configuring/Compiling/Installing CRTM.")
        # configure, comile and install CRTM to the installPath
        configureCompileInstallCrtm( installPath, fo, fe, scriptDir )
        
        print("Moving to {}".format( os.path.join(installPath,'crtm') ))
        # get rid of the version to make things easier later on for pycrtm
        os.rename(glob.glob(os.path.join(installPath,'crtm_v*'))[0], os.path.join(installPath,'crtm'))

        print("Copying coefficients to {}".format( os.path.join(installPath,'crtm','crtm_coef') ) )   
        # make the coef directory along with the install location
        os.makedirs( os.path.join(installPath,'crtm','crtm_coef') )

        # copy coefficients 
        moveCrtmCoefficients( installPath )

        # go back to script directory.
        os.chdir(scriptDir)

        # remove untarred directory/now useless mess 
        shutil.rmtree(glob.glob('REL-*')[0])
        print("Modifying crtm.cfg")
        modifyOptionsCfg( 'crtm.cfg', scriptDir, installPath )

    print("Making python modules.")
    # build python module
    # Set compile environment variables.
    #os.environ['LDFLAGS']= compilerFlags[arch]['LDFLAGS']
    os.environ['FCFLAGS'] = os.environ['FCFLAGS'] + compilerFlags[arch]['FCFLAGS2']
    os.environ['FFLAGS'] = os.environ['FCFLAGS']
    os.environ['FC'] = compilerFlags[arch]['Compiler']
    os.environ['ILOC'] = os.path.join(installPath,'crtm')
    os.environ['F2PY_COMPILER'] = compilerFlags[arch]['F2PY_COMPILER']
    os.environ['FORT'] = compilerFlags[arch]['Compiler']
    print("Making pycrtm module.")
    makeModule(fo, fe, scriptDir)
    os.chdir(scriptDir)
    
    fo.close()
    fe.close()
    print("Done!")

def checkInstallDirectory( options ):
    # check if rttov directory in install location exists. If it exists delete and recreate, otherwise make it.
    listOfPaths = glob.glob(os.path.join(options.install,'crtm*'))
    for p in listOfPaths:
        # if it is a directory, and we're installing crtm make sure it's clean by deleting it.
        if os.path.isdir(p) and a.rtinstall:
            shutil.rmtree( p )

def selectCompilerFlags(arch):
    compilerFlags = {}
    if(arch =='gfortran-openmp'):
        compilerFlags['gfortran-openmp']={}
        compilerFlags['gfortran-openmp']['Compiler']='gfortran'
        fullGfortranPath = which('gfortran')
        if(fullGfortranPath ==''): sys.exit("No gfotran found in path.")

        gccBinPath = os.path.split(fullGfortranPath)[0]
        gccPath = os.path.split(gccBinPath)[0]
        gccLibPath = os.path.join(gccPath,'lib64')
        #gccGompPath = os.path.join(gccPath,'lib','gcc')
        #gccGompPath = glob.glob(os.path.join(gccGompPath,'*'))[0]
        #gccGompPath = os.path.join(gccGompPath,'gcc')
        #gccGompPath = glob.glob(os.path.join(gccGompPath,'*'))[0]
        #gccGompPath = glob.glob(os.path.join(gccGompPath,'*'))[0]
        #gccGompPath = os.path.join(gccGompPath,'finclude')
        # bit to check what gcc version is available, if not > 6. Problem. exit.
        p = Popen(['gfortran','-dumpversion'], stdout = PIPE, stderr = PIPE) 
        p.wait()
        so,se = p.communicate() 
        if ( int(so.decode("utf-8").split('.')[0]) < 6 ):
            sys.exit("F2008 required. gcc >= 6")
         
        #if( not os.path.exists(os.path.join(gccGompPath, 'omp_lib.mod'))):
        #    sys.exit("Can't find gomp in {}. Correct GCC module loaded?".format(gccGompPath) )
        
        compilerFlags['gfortran-openmp']['FCFLAGS1']="-fimplicit-none -ffree-form -fPIC -fopenmp -fno-second-underscore -frecord-marker=4 -std=f2008"
        compilerFlags['gfortran-openmp']['FCFLAGS2']=""# -lgomp -I"+gccGompPath+" -L"+gccLibPath
        compilerFlags['gfortran-openmp']['LDFLAGS']="-Wall -g -shared -lgomp"
        compilerFlags['gfortran-openmp']['F2PY_COMPILER']="gnu95"
   
    elif(arch == 'ifort-openmp'):
        compilerFlags['ifort-openmp']={}
        compilerFlags['ifort-openmp']['Compiler']='ifort'
        fullIfortPath = which('ifort')

        if(fullIfortPath == ''): sys.exit("No ifort found.")

        compilerFlags['ifort-openmp']['FCFLAGS1']="-openmp -fPIC -liomp5 -O3 -fp-model source -e08 -free -assume byterecl,realloc_lhs"
        compilerFlags['ifort-openmp']['FCFLAGS2']=" -liomp5 "
        compilerFlags['ifort-openmp']['LDFLAGS']="-Wall -g -shared -liomp5"
        compilerFlags['ifort-openmp']['F2PY_COMPILER']='intelem'
    else:
        sys.exit('Unknown compiler {}.'.format(arch))   
    return compilerFlags
       
def downloadExtractTar( tarballPath, scriptDir ):
    if not os.path.exists(tarballPath):
        os.makedirs(tarballPath)
    os.chdir(tarballPath)
    if(len(glob.glob(os.path.join(tarballPath,'crtm_*.tar.gz')))==0):
        print("Downloading CRTM Tarball {}. This will likely take a while, because this server is *insanely* slow.".format ('http://ftp.emc.ncep.noaa.gov/jcsda/CRTM/REL-2.3.0/crtm_v2.3.0.tar.gz'))
        urllib.request.urlretrieve("http://ftp.emc.ncep.noaa.gov/jcsda/CRTM/REL-2.3.0/crtm_v2.3.0.tar.gz", "crtm_v2.3.0.tar.gz") 
    print("Untarring CRTM Tarball {}".format (glob.glob(os.path.join(tarballPath,'crtm_*.tar.gz'))[0]))
    t = tarfile.open( glob.glob(os.path.join(tarballPath,'crtm_*.tar.gz'))[0]  )
    t.extractall( path = scriptDir )
    t.close()
    os.chdir(scriptDir)

    
def runAndCheckProcess(p, name, fo, fe, scriptDir):
    if(p.returncode>0):
        foname = fo.name
        fename = fe.name

        with open(os.path.join(scriptDir,foname),'r') as foOb:
            for l in foOb.readlines():
                print( l.strip() )

        with open(os.path.join(scriptDir,fename),'r') as feOb:
            for l in feOb.readlines():
                print( l.strip() )

        print("For more information about the install look in {}, and {}".format(fo.name,fe.name) )
        fo.close()
        fe.close()
        sys.exit(name+" failed.")
def patchCrtm(fo, fe, scriptDir):
    # patch to fix gfortran incompatibility make some objects in/out
    p = Popen(['patch','-p0','-i',os.path.join(scriptDir,'gfortran.patch')],stderr=fe,stdout=fo)
    p.wait()
    runAndCheckProcess(p,"Patching CRTM for gcc compatibility ", fo, fe, scriptDir)

def configureCompileInstallCrtm( installLocation, fo, fe, scriptDir ):
    # configure as one usually does
    p = Popen(['./configure','--prefix='+installLocation,'--disable-big-endian'],stderr=fe,stdout=fo)
    p.wait()
    runAndCheckProcess(p,"CRTM configure", fo, fe, scriptDir)

    p = Popen(['make','-j'+a.jproc],stderr=fe,stdout=fo,shell=True)
    p.wait()
    runAndCheckProcess(p, "Comipling CRTM", fo, fe, scriptDir)
    
    p = Popen(['make', 'check'],stderr=fe,stdout=fo, shell=True)
    p.wait()
    runAndCheckProcess(p,"CRTM check", fo, fe, scriptDir)
    
    p = Popen(['make','install'],stderr=fe,stdout=fo)
    p.wait()        
    runAndCheckProcess(p,"CRTM install", fo, fe, scriptDir)

def moveCrtmCoefficients(installLocation):
    cwd = os.getcwd()
    p = os.path.join(cwd,'fix','SpcCoeff','Little_Endian')
    for f in os.listdir(p):
        shutil.copy(os.path.join(p,f), os.path.join(installLocation,'crtm','crtm_coef'))

    p = os.path.join(cwd,'fix','TauCoeff','ODPS','Little_Endian')
    for f in os.listdir(p):
        shutil.copy(os.path.join(p,f), os.path.join(installLocation,'crtm','crtm_coef'))

    p = os.path.join(cwd,'fix','CloudCoeff','Little_Endian') 
    for f in os.listdir(p):
        shutil.copy(os.path.join(p,f), os.path.join(installLocation,'crtm','crtm_coef'))
    
    p = os.path.join(cwd,'fix','AerosolCoeff','Little_Endian') 
    for f in os.listdir(p):
        shutil.copy(os.path.join(p,f), os.path.join(installLocation,'crtm','crtm_coef'))

    p = os.path.join(cwd,'fix','EmisCoeff','IR_Ice','SEcategory','Little_Endian') 
    for f in os.listdir(p):
        shutil.copy(os.path.join(p,f), os.path.join(installLocation,'crtm','crtm_coef'))

    p = os.path.join(cwd,'fix','EmisCoeff','IR_Land','SEcategory','Little_Endian') 
    for f in os.listdir(p):
        shutil.copy(os.path.join(p,f), os.path.join(installLocation,'crtm','crtm_coef'))

    p = os.path.join(cwd,'fix','EmisCoeff','IR_Snow','SEcategory','Little_Endian') 
    for f in os.listdir(p):
        shutil.copy(os.path.join(p,f), os.path.join(installLocation,'crtm','crtm_coef'))

    p = os.path.join(cwd,'fix','EmisCoeff','IR_Water','Little_Endian') 
    for f in os.listdir(p):
        shutil.copy(os.path.join(p,f), os.path.join(installLocation,'crtm','crtm_coef'))

    p = os.path.join(cwd,'fix','EmisCoeff','MW_Water','Little_Endian') 
    for f in os.listdir(p):
        shutil.copy(os.path.join(p,f), os.path.join(installLocation,'crtm','crtm_coef'))

    p = os.path.join(cwd,'fix','EmisCoeff','VIS_Ice','SEcategory','Little_Endian') 
    for f in os.listdir(p):
        shutil.copy(os.path.join(p,f), os.path.join(installLocation,'crtm','crtm_coef'))

    p = os.path.join(cwd,'fix','EmisCoeff','VIS_Land','SEcategory','Little_Endian') 
    for f in os.listdir(p):
        shutil.copy(os.path.join(p,f), os.path.join(installLocation,'crtm','crtm_coef'))

    p = os.path.join(cwd,'fix','EmisCoeff','VIS_Snow','SEcategory','Little_Endian') 
    for f in os.listdir(p):
        shutil.copy(os.path.join(p,f), os.path.join(installLocation,'crtm','crtm_coef'))

    p = os.path.join(cwd,'fix','EmisCoeff','VIS_Water','SEcategory','Little_Endian') 
    for f in os.listdir(p):
        shutil.copy(os.path.join(p,f), os.path.join(installLocation,'crtm','crtm_coef'))

def makeModule(fo, fe, scriptDir):
    # make pycrtm module
    os.chdir(scriptDir)

    p=Popen(['make', 'clean'],stderr=fe,stdout=fo)
    p.wait()
    runAndCheckProcess(p,'pycrtm make clean', fo, fe, scriptDir)
   
    p=Popen(['make'],stderr=fe,stdout=fo)
    p.wait()
    runAndCheckProcess(p,'pycrtm make', fo, fe, scriptDir)
    #os.system('./sourceMe.bash')
def makeLegacyInterpModule(fo, fe, scriptDir):
    p=Popen(['make', 'clean'],stderr=fe,stdout=fo)
    p.wait()
    runAndCheckProcess(p,'legacy_interp make clean', fo, fe, scriptDir)

    p=Popen(['make'],stderr=fe,stdout=fo)
    p.wait()
    runAndCheckProcess(p,'legacy_interp make', fo, fe, scriptDir)

def modifyOptionsCfg( filename, scriptDir, installLocation ):
    with open( filename ,'w') as newFile:
        with open(os.path.join(scriptDir, filename), 'r') as oldFile:
            for l in oldFile:
                if('coeffs_dir' in l):
                    newFile.write(l.replace(l,'coeffs_dir = '+os.path.join(installLocation,'crtm','crtm_coef')+os.linesep))
                else:
                    newFile.write(l)
    # move it up a directory.
    shutil.move(filename, os.path.join(os.path.split(scriptDir)[0], filename) )

def which(name):
    found = 0 
    for path in os.getenv("PATH").split(os.path.pathsep):
        full_path = path + os.sep + name
        if os.path.exists(full_path):
            found = 1
            return full_path
    return ''
if __name__ == "__main__":
    parser = argparse.ArgumentParser( description = 'install crtm and pycrtm')
    parser.add_argument('--install',help = 'install path.', required = True, dest='install')
    parser.add_argument('--rtpath',help = 'path to RT tarballs.', required = True, dest='rtpath')
    parser.add_argument('--jproc',help = 'Number of threads to pass to make.', required = True, dest='jproc')
    parser.add_argument('--arch',help = 'compiler/architecture.', required = False, dest='arch', default='gfortran-openmp')
    parser.add_argument('--inplace', help="Switch installer to use rtpath for previously installed crtm.", dest='rtinstall', action='store_false' )
    a = parser.parse_args()
    main(a)

