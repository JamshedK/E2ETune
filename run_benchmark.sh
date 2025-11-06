cd /home/farshedvardtgem22/E2ETune/benchbase/target/benchbase-postgres
# log the current directory
pwd
BENCHNAME=$1
TIMESTAMP=$2
OUTPUTDIR="$(realpath "$3")"  # Convert to absolute path
OUTPUTLOG="$(realpath "$4")"  # Convert to absolute path

java -jar benchbase.jar -b $BENCHNAME -c config/postgres/sample_${BENCHNAME}_config.xml --execute=true --directory=$OUTPUTDIR > ${OUTPUTLOG}/${BENCHNAME}_${TIMESTAMP}.log