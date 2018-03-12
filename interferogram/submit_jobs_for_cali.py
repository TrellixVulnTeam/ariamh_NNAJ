#!/usr/bin/env python
import os, sys, requests, json
from datetime import datetime
from pprint import pprint

from hysds.orchestrator import submit_job


def get_job(objectid):
    """Return json job configuration for NS/CI."""

    return {
        "job_type": "job:ariamh_sciflo_create_interferogram",
        "payload": {
            "objectid": objectid,
        }
    } 


def submit_jobs(es_url, mozart_url, job_queue, done_json):
    """Query all CSK scenes for California and submit NS/CI jobs."""

    done_dict = {}
    if os.path.exists(done_json):
        with open(done_json) as f:
            done_dict = json.load(f)

    query = {
        "query": {
            "bool": {
                "must": [
                    {
                        "term": {
                            "dataset": "CSK"
                        }
                    },
                    {
                        "term": {
                            "metadata.dfas.RequestorUserId.untouched": "MAPCALIFORNIA_CIDOT_JPL_2013"
                        }
                    },
                    {
                        "term": {
                            "system_version": "v0.3"
                        }
                    }
                ]
            }
        }
    }
    search_url = '%s/grq_csk/_search?search_type=scan&scroll=10m&size=100' % es_url
    r = requests.post(search_url, data=json.dumps(query))
    if r.status_code != 200:
        print >>stderr, "Failed to query %s:\n%s" % es_url
        print >>stderr, "query: %s" % json.dumps(query, indent=2)
        print >>stderr, "returned: %s" % r.text
    r.raise_for_status()
    scan_result = r.json()
    count = scan_result['hits']['total']
    scroll_id = scan_result['_scroll_id']
    #pprint(scan_result)
    submitted = 0
    while True:
        r = requests.post('%s/_search/scroll?scroll=10m' % es_url, data=scroll_id)
        res = r.json()
        scroll_id = res['_scroll_id']
        #pprint(res)
        if len(res['hits']['hits']) == 0: break
        for hit in res['hits']['hits']:
            id = hit['_id']
            if id in done_dict: continue
            job_json = get_job(id)
            submit_job.apply_async((job_json,), queue=job_queue)
            done_dict[id] = True
            submitted += 1
    print "Submitted %s jobs for NS/CI workflows over California." % submitted

    with open(done_json, 'w') as f:
        json.dump(done_dict, f, indent=2, sort_keys=True)


if __name__ == "__main__":
    es_url = 'http://aria-products.jpl.nasa.gov:9200'
    mozart_url = 'amqp://guest:guest@aria-jobs.jpl.nasa.gov:5672//'
    job_queue = 'jobs_processed'
    done_json = 'cali_jobs.json'
    submit_jobs(es_url, mozart_url, job_queue, done_json)
