#!/usr/bin/python

import re
import commands
import pyodbc
import sys
import json

PLUGIN_NAME='PostgreSQL'

CONFIG_PARAMS = [
	# ('config key', 'name', 'required'),
	('postgres_database', 'PostgreSQLDatabase', True),
	('postgres_user', 'PostgreSQLUser', True),
	('postgres_pass', 'PostgreSQLPassword', True),
	('postgres_host', 'PostgreSQLHost', True),
	('postgres_port', 'PostgreSQLPort', False),
	('postgres_odbcdriver', 'PostgresODBCDriver', True),
]
PLUGIN_STATS = [
#	'postgresVersion',
	'postgresMaxConnections',
	'postgresCurrentConnections',
	'postgresTransactionLocks',
	'postgresTableLocks',
	'postgresAvailableConnections'
]

#===============================================================================
class PostgreSQL:
	#---------------------------------------------------------------------------
	def __init__(self, agent_config, checks_logger, raw_config):
		self.agent_config = agent_config
		self.checks_logger = checks_logger
		self.raw_config = raw_config

		# get config options

		if self.raw_config != None:
			if self.raw_config.get('PostgreSQL', False):
				for key, name, required in CONFIG_PARAMS:
					self.agent_config[name] = self.raw_config['PostgreSQL'].get(key, None)
			else:
				self.checks_logger.debug(
					'%s: Postgres config section missing ([PostgreSQL]' % PLUGIN_NAME
				)
				
		# reset plugin specific params
		for param in PLUGIN_STATS:
			self.param = None 
		#setattr(self, param, None)

	#---------------------------------------------------------------------------
	def run(self):
		# make sure we have the necessary config params
		if self.agent_config != None:
			for key, name, required in CONFIG_PARAMS:
				if required and not self.agent_config.get(name, False):
					self.checks_logger.debug(
						'%s: config not complete (missing: %s) under PostgreSQL' % (
							PLUGIN_NAME,
							key
						)
					)
					return False

		# connect using pyodbc
		try:
			db = pyodbc.connect('DRIVER={' + str(self.agent_config['PostgresODBCDriver']) + '};SERVER=' + str(self.agent_config['PostgreSQLHost']) + ';DATABASE=' +  str(self.agent_config['PostgreSQLDatabase']) + ';UID=' +  str(self.agent_config['PostgreSQLUser']) + ';PWD=' + str(self.agent_config['PostgreSQLPassword']) + ';')
		except:
			self.checks_logger.error(
				'%s: PostgreSQL connection error: %s' % (PLUGIN_NAME, sys.exc_info()[0])
			)
			return False

		# get max connections
		try:
			cursor = db.cursor()
			cursor.execute(
				"SELECT setting AS mc FROM pg_settings WHERE name = 'max_connections'"
			)
			self.postgresMaxConnections = int(cursor.fetchone()[0])
		except:
			self.checks_logger.error(
				'%s: SQL query error when getting max connections: %s' % (PLUGIN_NAME, sys.exc_info()[0])
			)
		#Current Connections
		try:
			cursor = db.cursor()
			cursor.execute("SELECT COUNT(datid) FROM pg_database AS d LEFT JOIN pg_stat_activity AS s ON (s.datid = d.oid)")
			self.postgresCurrentConnections = int(cursor.fetchone()[0])
		except pyodbc.ProgrammingError, e:
			self.checks_logger.error(
				'%s: SQL query error when getting current connections: %s' % (PLUGIN_NAME, sys.exc_info()[0])
			)

		#Get transaction locks
		try:
			cursor = db.cursor()
			cursor.execute("Select count(*) from (Select locked.pid as locked_pid, locker.pid as locker_pid,locked_act.usename as locked_uuser,locker_act.usename as locker_user,locked.virtualtransaction,locked.transactionid,locked.locktype from pg_locks locked ,pg_locks locker,pg_stat_activity locked_act,pg_stat_activity locker_act WHERE locker.granted = true and locked.granted = false and locked.pid = locked_act.pid and locker.pid = locker_act.pid and(locked.virtualtransaction=locker.virtualtransaction or locked.transactionid= locker.transactionid)) transactionlocks;")
			response = int(cursor.fetchone()[0])
			self.postgresTransactionLocks = response
		except pyodbc.ProgrammingError, e:
			self.checks_logger.error('%s: SQL query error when getting transaction locks: %s' % (PLUGIN_NAME, e))
			#print e
		#Get Table locks
		try:
			cursor = db.cursor()
			cursor.execute("select count(*) from(Select locked.pid as locked_pid,locker.pid as locker_pid,locked_act.usename as locked_user,locker_act.usename as locker_user,locked.virtualtransaction,locked.transactionid,relname from pg_locks locked LEFT OUTER JOIN pg_class on locked.relation = pg_class.oid,pg_locks locker,pg_stat_activity locked_act,pg_stat_activity locker_act WHERE locker.granted = true and locked.granted = false and locked.pid = locked_act.pid and locker.pid = locker_act.pid and locked.relation=locker.relation) tablelocks;")
			self.postgresTableLocks = int(cursor.fetchone()[0])
		except pyodbc.ProgrammingError, e:
			self.checks_logger.error('%s: SQL query error when getting transaction locks: %s' % (PLUGIN_NAME, e))
	
		#Calculate Connections available for use
		self.postgresAvailableConnections = int(self.postgresMaxConnections) - int(self.postgresCurrentConnections)

		# return the stats
		stats = {}
		for param in PLUGIN_STATS:
			stats[param] = getattr(self, param, None)

		#Uncomment to test connection string
		#stats['connectionstring'] = 'DRIVER={' + str(self.agent_config['PostgresODBCDriver']) + '};SERVER=' + str(self.agent_config['PostgreSQLHost']) + ';DATABASE=' +  str(self.agent_config['PostgreSQLDatabase']) + ';UID=' +  str(self.agent_config['PostgreSQLUser']) + ';PWD=' + str(self.agent_config['PostgreSQLPassword']) + ';'
		return stats
		
		
	
if __name__ == "__main__":
	postgres = PostgreSQL(None, None, None)
	print postgres.run()
