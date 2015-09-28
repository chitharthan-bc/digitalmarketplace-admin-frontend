try:
    from urlparse import urlsplit
    from StringIO import StringIO
except ImportError:
    from urllib.parse import urlsplit
    from io import BytesIO as StringIO
import mock
from lxml import html
from ...helpers import LoggedInApplicationTest


@mock.patch('app.main.views.users.data_api_client')
class TestUsersView(LoggedInApplicationTest):

    def test_should_be_a_404_if_user_not_found(self, data_api_client):
        data_api_client.get_user.return_value = None
        response = self.client.get('/admin/users?email_address=some@email.com')
        self.assertEquals(response.status_code, 404)

        document = html.fromstring(response.get_data(as_text=True))

        page_title = document.xpath(
            '//p[@class="banner-message"]//text()')[0].strip()
        self.assertEqual("Sorry, we couldn't find an account with that email address", page_title)

        page_title = document.xpath(
            '//p[@class="summary-item-no-content"]//text()')[0].strip()
        self.assertEqual("No users to show", page_title)

    def test_should_be_a_404_if_no_email_provided(self, data_api_client):
        data_api_client.get_user.return_value = None
        response = self.client.get('/admin/users?email_address=')
        self.assertEquals(response.status_code, 404)

        document = html.fromstring(response.get_data(as_text=True))

        page_title = document.xpath(
            '//p[@class="banner-message"]//text()')[0].strip()
        self.assertEqual("Sorry, we couldn't find an account with that email address", page_title)

        page_title = document.xpath(
            '//p[@class="summary-item-no-content"]//text()')[0].strip()
        self.assertEqual("No users to show", page_title)

    def test_should_be_a_404_if_no_email_param_provided(self, data_api_client):
        data_api_client.get_user.return_value = None
        response = self.client.get('/admin/users')
        self.assertEquals(response.status_code, 404)

        document = html.fromstring(response.get_data(as_text=True))

        page_title = document.xpath(
            '//p[@class="banner-message"]//text()')[0].strip()
        self.assertEqual("Sorry, we couldn't find an account with that email address", page_title)

        page_title = document.xpath(
            '//p[@class="summary-item-no-content"]//text()')[0].strip()
        self.assertEqual("No users to show", page_title)

    def test_should_show_buyer_user(self, data_api_client):
        buyer = self.load_example_listing("user_response")
        buyer.pop('supplier', None)
        buyer['users']['role'] = 'buyer'
        data_api_client.get_user.return_value = buyer
        response = self.client.get('/admin/users?email_address=test.user@sme.com')
        self.assertEquals(response.status_code, 200)

        document = html.fromstring(response.get_data(as_text=True))

        email_address = document.xpath(
            '//header[@class="page-heading page-heading-without-breadcrumb"]//h1/text()')[0].strip()
        self.assertEqual("test.user@sme.com", email_address)

        name = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/text()')[0].strip()
        self.assertEqual("Test User", name)

        role = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/text()')[1].strip()
        self.assertEqual("buyer", role)

        supplier = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/text()')[2].strip()
        self.assertEquals('', supplier)

        last_login = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/text()')[3].strip()
        self.assertEquals('10:33:53', last_login)

        last_login_day = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/text()')[4].strip()
        self.assertEquals('23 July', last_login_day)

        last_password_changed = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/text()')[5].strip()
        self.assertEquals('13:46:01', last_password_changed)

        last_password_changed_day = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/text()')[6].strip()
        self.assertEquals('29 June', last_password_changed_day)

        locked = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/text()')[7].strip()
        self.assertEquals('No', locked)

        button = document.xpath(
            '//input[@class="button-destructive"]')[0].value
        self.assertEquals('Deactivate', button)

    def test_should_show_supplier_user(self, data_api_client):
        buyer = self.load_example_listing("user_response")
        data_api_client.get_user.return_value = buyer
        response = self.client.get('/admin/users?email_address=test.user@sme.com')
        self.assertEquals(response.status_code, 200)

        document = html.fromstring(response.get_data(as_text=True))

        email_address = document.xpath(
            '//header[@class="page-heading page-heading-without-breadcrumb"]//h1/text()')[0].strip()
        self.assertEqual("test.user@sme.com", email_address)

        role = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/text()')[1].strip()
        self.assertEqual("supplier", role)

        supplier = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/a/text()')[0].strip()
        self.assertEquals('SME Corp UK Limited', supplier)

        supplier_link = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/a')[0]
        self.assertEquals('/admin/suppliers/users?supplier_id=1000', supplier_link.attrib['href'])

    def test_should_show_unlock_button(self, data_api_client):
        buyer = self.load_example_listing("user_response")
        buyer['users']['locked'] = True

        data_api_client.get_user.return_value = buyer
        response = self.client.get('/admin/users?email_address=test.user@sme.com')
        self.assertEquals(response.status_code, 200)

        document = html.fromstring(response.get_data(as_text=True))

        unlock_button = document.xpath(
            '//input[@class="button-secondary"]')[0].attrib['value']
        unlock_link = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/form')[0]
        return_link = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/form/input')[1]
        self.assertEquals('/admin/suppliers/users/999/unlock', unlock_link.attrib['action'])
        self.assertEquals('Unlock', unlock_button)
        self.assertEquals('/admin/users?email_address=test.user%40sme.com', return_link.attrib['value'])

    def test_should_show_deactivate_button(self, data_api_client):
        buyer = self.load_example_listing("user_response")

        data_api_client.get_user.return_value = buyer
        response = self.client.get('/admin/users?email_address=test.user@sme.com')
        self.assertEquals(response.status_code, 200)

        document = html.fromstring(response.get_data(as_text=True))

        deactivate_button = document.xpath(
            '//input[@class="button-destructive"]')[0].attrib['value']
        deactivate_link = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/form')[0]
        return_link = document.xpath(
            '//tr[@class="summary-item-row"]//td/span/form/input')[1]
        self.assertEquals('/admin/suppliers/users/999/deactivate', deactivate_link.attrib['action'])
        self.assertEquals('Deactivate', deactivate_button)
        self.assertEquals('/admin/users?email_address=test.user%40sme.com', return_link.attrib['value'])