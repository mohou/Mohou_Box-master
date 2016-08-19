#!/bin/bash
HOME_DIR="/home/pi"
ROOT_DIR="${HOME_DIR}/oprint/lib/python2.7/site-packages/"
VER=`ls -1 ${ROOT_DIR} | grep boxUpdate | cut -d'-' -f2`

/bin/tar zcvf $1  ${ROOT_DIR}/boxUpdate-${VER}-py2.7.egg/logs ${ROOT_DIR}/boxAgent-${VER}-py2.7.egg/logs ${ROOT_DIR}/boxPrint-${VER}-py2.7.egg/logs ${HOME_DIR}/.update /var/log/

