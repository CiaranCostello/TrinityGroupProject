from docker import Client
from docker import errors
import argparse
import yaml
import pprint

def command_setup(subparser):
	subparser.add_argument('-c', '--config', required=True, help='yaml file describing the application')
	subparser.add_argument('-m', '--manager', required=True, help='sepcify the host and port of the docker manager eg 127.0.0.1:3000')
	subparser.add_argument('-q', '--quiet', required=False, help='Supress messages from the script')

#allows us to specify the command line arguments that the script must recieve in order to execute
def clargs():
	main_parser = argparse.ArgumentParser(description='a script to start an application on a distributed swarm network')
	# required = parser.add_argument_group('required arguments')
	sub_parser = main_parser.add_subparsers(dest='cmd')
	sub_parser.required = True
	#sub commands for the program
	start = sub_parser.add_parser('start', help='start an application')
	command_setup(start)
	start.add_argument('-n', '--network', help='Name of the overlay network', default='dockernet')
	stop = sub_parser.add_parser('stop', help='stop an application')
	command_setup(stop)
	cc = sub_parser.add_parser('cc', help='clear all containers from swarm')
	command_setup(cc)

	return main_parser.parse_args()

class Swarmpose():
	def createOverlayNetwork(self, name):
		self.cli.create_network(name=name, driver="overlay")

	def networkExists(self, network):
		networks = self.cli.networks(names=[network])
		return (len(networks) != 0)

	#initialise the swarmpose class
	def __init__(self, yamal, manager, network="dockernet"):
		self.yamal = yamal
		self.HOST, self.PORT = manager.split(':')
		#Connect to remote daemon
		self.cli = Client(base_url='tcp://' + self.HOST + ':' + self.PORT)
		#parse the yaml file into a dictionary of dictionaries
		self.nodes = self.parseFile(yamal)
		#check if an overlay network exists if not create one (default='Dockernet')
		self.network = network
		if (self.networkExists(network) != True):
			self.createOverlayNetwork(network)

	#parse the yamal file and return a dictionary
	def parseFile(self, file):
		with open(file, 'r') as fh:
			nodes=yaml.load(fh)
			return nodes

	def killAllTheContainers(self):
		#don't look back!
	  print("**** Clearing Containers ****")
	  for name,val in self.nodes.items():
	    try:
	      print ("Purging " + name + "...")
	      self.cli.remove_container(name, force=True)
	    except errors.NotFound as e:
	      print(e.explanation.decode('UTF-8'))

	def runImage(self, name, image, ports, links=None):
		try:
			container = self.cli.create_container(image=image, ports=ports, name=name, host_config=self.cli.create_host_config(network_mode=self.network))
			self.cli.start(container=container.get('Id'))
			result = self.cli.inspect_container(container=container.get('Id'))
			print ("Started " + name + " on " + result['Node']['Addr'])
			return container.get('Id')
		except errors.APIError as e:
			print(e.explanation.decode('UTF-8'))

	def stopImage(self, container):
		print("Stopping image "+ container)
		self.cli.stop(container)

	def start(self):
		print('**** Starting Application on Swarm ****')
		#seperate our nodes into two dictionaries, the starting_nodes wich have no dependancies and
		#remaining nodes which have dependancies
		starting_nodes = {name:config for name,config in self.nodes.items() if 'links' not in config}
		remaining_nodes = {name:self.nodes[name] for name  in self.nodes.keys() if name not in starting_nodes.keys()}

		#Create a dictionary to indcate the nodes that have been started
		nodes_run = {}
		for name in starting_nodes:
			test = self.runImage(name, self.nodes[name]['image'], self.nodes[name]['expose'])
		nodes_run.update(starting_nodes)
		#keep runnng until all nodes have been run
		while len(nodes_run) != len(self.nodes):
			#get the next dictionary of nodes that depend on the starting nodes
			next_nodes_2run = self.nextNodesRunning(remaining_nodes, nodes_run)
			for name in next_nodes_2run:
				test = self.runImage(name, self.nodes[name]['image'], self.nodes[name]['expose'], self.nodes[name]['links'])
			nodes_run.update(next_nodes_2run)
			remaining_nodes = {name:self.nodes[name] for name in self.nodes.keys() if name not in nodes_run.keys()}

	def stop(self):
		print('**** Stopping Application ****')
		can_stop=True
		nodes_stopped={}
		while(len(nodes_stopped)!=len(self.nodes)):
			for temp, config in self.nodes.items():
				for name, values in self.nodes.items():
					if(temp in 'links') :
						if(inspect_container(name)):
							can_stop=False
				if(can_stop == True and temp not in nodes_stopped):
					nodes_stopped[temp] = config
					self.stopImage(temp)



	def nextNodesRunning(self, remaining_nodes, nodes_ran):
		#get the next dictionary of nodes that depend on the starting nodes
		next_nodes_run = {}
		for name, config in remaining_nodes.items():
			if set(config['links']).issubset(set(list(nodes_ran.keys()))):
				next_nodes_run[name] = config
				return next_nodes_run

if __name__ == '__main__':
	args = clargs()
	if(args.cmd == 'start'):
		Swarmpose(args.config, args.manager, args.network).start()
	elif(args.cmd == 'cc'):
		Swarmpose(args.config, args.manager).killAllTheContainers()
	else:
		Swarmpose(args.config, args.manager).stop()
