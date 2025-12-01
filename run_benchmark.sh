cd /home/farshedvardtgem22/E2ETune/benchbase/target/benchbase-postgres
# log the current directory
pwd
BENCHNAME=$1
TIMESTAMP=$2
OUTPUTDIR="$(realpath "$3")"  # Convert to absolute path
OUTPUTLOG="$(realpath "$4")"  # Convert to absolute path
CONFIGFILE=${5:-"sample_${BENCHNAME}_config.xml"}  # Use provided config or default

java -jar benchbase.jar -b $BENCHNAME -c config/postgres/$CONFIGFILE --execute=true --directory=$OUTPUTDIR > ${OUTPUTLOG}/${BENCHNAME}_${TIMESTAMP}.log