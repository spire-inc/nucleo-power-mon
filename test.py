from nucleo_power import PowerMon
import logging

logging.getLogger().setLevel(logging.DEBUG)
logging.basicConfig(
        filename=None,
        format='%(asctime)s |%(levelname)7s |%(name)20s | %(message)s')

pm = PowerMon()
#pm._helloworld()
pm.start(duration = 3)
pm.close()


