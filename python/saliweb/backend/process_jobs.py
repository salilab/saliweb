def main(webservice):
    web = webservice.get_web_service(webservice.config)
    web.do_all_processing()
