#!/usr/bin/python3

import boto3
import datetime
import pytz
import argparse
import logging


def list_rogue_machines(timeout):
    logger = logging.getLogger("aws_cleaner.list")
    instances = []
    ec2client = boto3.client('ec2', region_name='us-east-1')
    ec2 = boto3.resource('ec2', region_name='us-east-1')
    desc = ec2client.describe_instances(
        Filters=[
            {
                'Name': 'tag:Workload',
                'Values': ['CI Runner']
            }
        ]
    )
    utc = pytz.UTC
    now = utc.localize(datetime.datetime.now())
    for resa in desc["Reservations"]:
        for instance in resa["Instances"]:
            iid = instance["InstanceId"]
            launch_time = instance["LaunchTime"]
            state = instance["State"]
            launch_timeout = launch_time + datetime.timedelta(hours=timeout)
            if now > launch_timeout and "terminated" not in state['Name']:
                instances.append([ec2.Instance(iid)][0])
                upsince = now - launch_time
                logger.info(f"%s up since %s %s",
                            iid,
                            upsince,
                            state)
    return instances


def kill_rogue_instances(instances):
    logger = logging.getLogger("aws_cleaner.kill")
    # iterate through instance IDs and terminate them
    for instance in instances:
        response = instance.terminate()
        logger.info("%s: current state %s",
                    instance,
                    response["TerminatingInstances"][0]["CurrentState"]["Name"])


def main():
    parser = argparse.ArgumentParser(
        description="Detect/kill rogue CI machines"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARN"],
        default="INFO",
        type=str,
        help="log level"
    )
    parser.add_argument(
        "--timeout",
        default=4,
        type=int,
        help="time in hours after launch time to consider an instance rogue"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Do not kill, just list rogue machines"
    )

    FORMAT = "%(asctime)s %(name)s/%(levelname)s: %(message)s"
    args = parser.parse_args()
    if "DEBUG" in args.log_level:
        logging.basicConfig(format=FORMAT, encoding='utf-8',
                            level=logging.DEBUG)
    if "INFO" in args.log_level:
        logging.basicConfig(
            format=FORMAT, encoding='utf-8', level=logging.INFO)
    if "WARN" in args.log_level:
        logging.basicConfig(format=FORMAT, encoding='utf-8',
                            level=logging.WARNING)
    logger = logging.getLogger("aws_cleaner.main")
    try:
        rogue_instances = list_rogue_machines(args.timeout)
        if rogue_instances:
            if args.dry_run:
                logger.info("no killing, dry run mode")
                return
            else:
                logger.info("Killing %d instances", len(rogue_instances))
                kill_rogue_instances(rogue_instances)
        else:
            logger.info("no rogue instances")
    except Exception as e:
        logger.error(e)
        logger.error("Check AWS credentials")


if __name__ == "__main__":
    main()
