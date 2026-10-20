#!/bin/bash
for i in {1..10}; do
  # curl -s -o /dev/null -w "%{http_code}|%{time_total}\n" https://uwa-policy.cits5501.arranstewart.io/policy/
  curl -D "header-$i.txt" -o "body$i" https://uwa-policy.cits5501.arranstewart.io/policy/
  echo '-----------------------'
done
