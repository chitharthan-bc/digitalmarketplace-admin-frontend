from functools import partial

import pytest

try:
    from urlparse import urlsplit
    from StringIO import StringIO
except ImportError:
    from urllib.parse import urlsplit
    from io import BytesIO as StringIO
from itertools import chain
import mock

from flask import Markup
from lxml import html
from six import text_type

from dmapiclient import HTTPError
from dmapiclient.audit import AuditTypes
from dmutils import s3

from tests.app.main.helpers.flash_tester import assert_flashes
from ...helpers import LoggedInApplicationTest


class TestServiceFind(LoggedInApplicationTest):

    def test_service_find_redirects_to_view_for_valid_service_id(self):
        response = self.client.get('/admin/services?service_id=314159265')
        assert response.status_code == 302
        assert "/services/314159265" in response.location

    def test_service_find_returns_404_for_missing_service_id(self):
        response = self.client.get('/admin/services')
        assert response.status_code == 404


@mock.patch('app.main.views.services.data_api_client', autospec=True)
class TestServiceView(LoggedInApplicationTest):
    user_role = 'admin-ccs-category'

    find_audit_events_api_response = {'auditEvents': [
        {
            'createdAt': '2017-11-17T11:22:09.459945Z',
            'user': 'anne.admin@example.com',
            'type': 'update_service_status',
            'data': {
                'new_status': "disabled",
                'old_status': 'published',
                'serviceId': '314159265'
            }
        },
        {
            'createdAt': '2017-11-16T11:22:09.459945Z',
            'user': 'bob.admin@example.com',
            'type': 'update_service_status',
            'data': {
                'new_status': "published",
                'old_status': 'private',
                'serviceId': '314159265'
            }
        },
    ]}

    # def test_service_view_status_disabled(self, data_api_client):
    #     data_api_client.get_service.return_value = {'services': {
    #         'frameworkSlug': 'g-cloud-8',
    #         'serviceName': 'test',
    #         'supplierId': 1000,
    #         'lot': 'iaas',
    #         'id': "314159265",
    #         "status": "disabled",
    #     }}
    #     data_api_client.find_audit_events.return_value = self.find_audit_events_api_response
    #     response = self.client.get('/admin/services/314159265')
    #
    #     assert response.status_code == 200
    #     assert data_api_client.get_service.call_args_list == [
    #         (("314159265",), {}),
    #     ]
    #     assert data_api_client.find_audit_events.call_args_list == [
    #         mock.call(
    #             audit_type=AuditTypes.update_service_status,
    #             latest_first='true',
    #             object_id='314159265',
    #             object_type='services'
    #         )
    #     ]
    #
    #     document = html.fromstring(response.get_data(as_text=True))
    #     assert document.xpath(
    #         "normalize-space(string(//td[@class='summary-item-field']//*[@class='service-id']))"
    #     ) == "314159265"
    #
    # def test_service_view_status_enabled(self, data_api_client):
    #     data_api_client.get_service.return_value = {'services': {
    #         'frameworkSlug': 'g-cloud-7',
    #         'serviceName': 'test',
    #         'supplierId': 1000,
    #         'lot': 'iaas',
    #         'id': "1412",
    #         "status": "enabled",
    #     }}
    #     data_api_client.find_audit_events.return_value = self.find_audit_events_api_response
    #     response = self.client.get('/admin/services/1412')
    #
    #     assert response.status_code == 200
    #     assert data_api_client.get_service.call_args_list == [
    #         (("1412",), {}),
    #     ]
    #     assert data_api_client.find_audit_events.call_args_list == [
    #         mock.call(
    #             audit_type=AuditTypes.update_service_status,
    #             latest_first='true',
    #             object_id='1412',
    #             object_type='services'
    #         )
    #     ]
    #
    #     document = html.fromstring(response.get_data(as_text=True))
    #     assert document.xpath(
    #         "normalize-space(string(//td[@class='summary-item-field']//*[@class='service-id']))"
    #     ) == "1412"
    @pytest.mark.parametrize('service_status', ['disabled', 'enabled', 'published'])
    def test_service_view_with_data(self, data_api_client, service_status):
        service = {
            'frameworkSlug': 'g-cloud-8',
            'lot': 'iaas',
            'id': "151",
            "status": service_status,
            "serviceName": "Saint Leopold's",
            "serviceFeatures": [
                "Rabbitry and fowlrun",
                "Dovecote",
                "Botanical conservatory",
            ],
            "serviceBenefits": [
                "Mentioned in court and fashionable intelligence",
            ],
            "supplierId": 1000,
            "deviceAccessMethod": {
                "value": [
                    "Corporate/enterprise devices",
                    "Unknown devices",
                ],
                "assurance": "Independent validation of assertion",
            },
        }
        data_api_client.get_service.return_value = {'services': service}
        data_api_client.find_audit_events.return_value = self.find_audit_events_api_response
        response = self.client.get('/admin/services/151')

        assert data_api_client.get_service.call_args_list == [
            (("151",), {}),
        ]
        assert response.status_code == 200

        document = html.fromstring(response.get_data(as_text=True))
        assert document.xpath(
            "normalize-space(string(//td[@class='summary-item-field']//*[@class='service-id']))"
        ) == "151"

        # check all serviceFeatures appear in an ul
        xpath_kwargs = {"a{}".format(i): term for i, term in enumerate(service["serviceFeatures"])}
        xpath_preds = "".join(
            "[./li[normalize-space(string())=$a{}]]".format(i) for i in range(len(service["serviceFeatures"]))
        )
        assert document.xpath(
            "//ul[count(./li)=$n_lis]{}".format(xpath_preds),
            n_lis=len(service["serviceFeatures"]),
            **xpath_kwargs
        )

        # ensure serviceBenefits is shown in a non-list-form
        assert document.xpath(
            "//*[@class='summary-item-field'][not(.//li)][normalize-space(string())=$s]",
            s=service["serviceBenefits"][0],
        )

        xpath_kwargs = {"a{}".format(i): term for i, term in enumerate(service["deviceAccessMethod"]["value"])}
        xpath_preds = "".join(
            "[./li[normalize-space(string())=$a{}]]".format(i)
            for i in range(len(service["deviceAccessMethod"]["value"]))
        )
        assert document.xpath(
            "//*[normalize-space(string())=$fullstr]/ul[count(./li)=$n_lis]{}".format(xpath_preds),
            fullstr=" ".join(chain(
                service["deviceAccessMethod"]["value"],
                ("Assured by", service["deviceAccessMethod"]["assurance"],),
            )),
            n_lis=len(service["deviceAccessMethod"]),
            **xpath_kwargs
        )

    @pytest.mark.parametrize(
        ('service_status', 'called'),
        [
            ('disabled', True),
            ('enabled', True),
            ('published', False)
        ]
    )
    def test_find_audit_events_not_called_for_published(self, data_api_client, service_status, called):
        service = {
            'frameworkSlug': 'g-cloud-8',
            'lot': 'iaas',
            'id': "151",
            "status": service_status,
            "serviceName": "Saint Leopold's",
            "serviceFeatures": [
                "Rabbitry and fowlrun",
                "Dovecote",
                "Botanical conservatory",
            ],
            "serviceBenefits": [
                "Mentioned in court and fashionable intelligence",
            ],
            "supplierId": 1000,
            "deviceAccessMethod": {
                "value": [
                    "Corporate/enterprise devices",
                    "Unknown devices",
                ],
                "assurance": "Independent validation of assertion",
            },
        }
        data_api_client.get_service.return_value = {'services': service}
        data_api_client.find_audit_events.return_value = self.find_audit_events_api_response
        response = self.client.get('/admin/services/151')

        assert response.status_code == 200
        assert data_api_client.find_audit_events.called is called

    @pytest.mark.parametrize('service_status', ['disabled', 'enabled'])
    def test_service_view_shows_info_banner_for_removed_and_private_services(self, data_api_client, service_status):
        data_api_client.get_service.return_value = {'services': {
            'frameworkSlug': 'g-cloud-8',
            'serviceName': 'test',
            'lot': 'iaas',
            'id': "314159265",
            'supplierId': 1000,
            "status": service_status,
        }}
        data_api_client.find_audit_events.return_value = self.find_audit_events_api_response

        response = self.client.get('/admin/services/314159265')
        page_content = response.get_data(as_text=True)
        document = html.fromstring(response.get_data(as_text=True))

        assert len(document.xpath("//div[@class='banner-temporary-message-without-action']/h2")) == 1
        # Xpath doesn't handle non-breaking spaces well, so assert against page_content
        assert 'Removed by anne.admin@example.com on Friday&nbsp;17&nbsp;November&nbsp;2017.' in page_content
        assert data_api_client.find_audit_events.call_args_list == [
            mock.call(
                latest_first="true",
                object_id='314159265',
                object_type="services",
                audit_type=AuditTypes.update_service_status
            )
        ]

    @pytest.mark.parametrize('service_status', ['disabled', 'enabled'])
    def test_info_banner_contains_publish_link_for_ccs_category(self, data_api_client, service_status):
        data_api_client.get_service.return_value = {'services': {
            'frameworkSlug': 'g-cloud-8',
            'serviceName': 'test',
            'lot': 'iaas',
            'id': "314159265",
            'supplierId': 1000,
            "status": service_status,
        }}
        data_api_client.find_audit_events.return_value = self.find_audit_events_api_response

        response = self.client.get('/admin/services/314159265')
        assert response.status_code == 200

        document = html.fromstring(response.get_data(as_text=True))
        expected_link_text = "Publish service"
        expected_href = '/admin/services/314159265?publish=True'
        expected_link = document.xpath('.//a[contains(@href,"{}")]'.format(expected_href))[0]

        assert expected_link.text == expected_link_text

    def test_service_view_does_not_show_info_banner_for_public_services(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'frameworkSlug': 'g-cloud-8',
            'serviceName': 'test',
            'lot': 'iaas',
            'id': "314159265",
            'supplierId': 1000,
            "status": 'published',
        }}
        data_api_client.find_audit_events.return_value = self.find_audit_events_api_response

        response = self.client.get('/admin/services/314159265')

        document = html.fromstring(response.get_data(as_text=True))
        assert len(document.xpath("//div[@class='banner-temporary-message-without-action']/h2")) == 0
        assert data_api_client.find_audit_events.called is False

    @pytest.mark.parametrize('service_status', ['disabled', 'enabled', 'published'])
    def test_service_view_hides_information_banner_if_no_audit_events(self, data_api_client, service_status):
        data_api_client.get_service.return_value = {'services': {
            'frameworkSlug': 'g-cloud-8',
            'serviceName': 'test',
            'lot': 'iaas',
            'id': "314159265",
            'supplierId': 1000,
            "status": service_status,
        }}
        data_api_client.find_audit_events.return_value = {'auditEvents': []}

        response = self.client.get('/admin/services/314159265')

        document = html.fromstring(response.get_data(as_text=True))
        assert len(document.xpath("//div[@class='banner-temporary-message-without-action']/h2")) == 0

    def test_redirect_with_flash_for_api_client_404(self, data_api_client):
        response = mock.Mock()
        response.status_code = 404
        data_api_client.get_service.side_effect = HTTPError(response)
        data_api_client.find_audit_events.return_value = self.find_audit_events_api_response

        response1 = self.client.get('/admin/services/1')
        assert response1.status_code == 302
        assert response1.location == 'http://localhost/admin'
        response2 = self.client.get(response1.location)
        assert b'Error trying to retrieve service with ID: 1' in response2.data

    def test_service_not_found_flash_message_injection(self, data_api_client):
        """
        Asserts that raw HTML in a bad service ID cannot be injected into a flash message.
        """
        # impl copied from test_redirect_with_flash_for_api_client_404
        api_response = mock.Mock()
        api_response.status_code = 404
        data_api_client.get_service.side_effect = HTTPError(api_response)
        data_api_client.find_audit_events.return_value = self.find_audit_events_api_response

        response1 = self.client.get('/admin/services/1%3Cimg%20src%3Da%20onerror%3Dalert%281%29%3E')
        response2 = self.client.get(response1.location)
        assert response2.status_code == 200

        html_response = response2.get_data(as_text=True)
        assert "1<img src=a onerror=alert(1)>" not in html_response
        assert "1&lt;img src=a onerror=alert(1)&gt;" in html_response

    def test_independence_of_viewing_services(self, data_api_client):
        data_api_client.find_audit_events.return_value = self.find_audit_events_api_response
        data_api_client.get_service.return_value = {'services': {
            'lot': 'SCS',
            'frameworkSlug': 'g-cloud-8',
            'serviceName': 'test',
            'supplierId': 1000,
            'id': "1",
            'status': 'published'
        }}
        response = self.client.get('/admin/services/1')
        assert b'Termination cost' in response.data

        data_api_client.get_service.return_value = {'services': {
            'lot': 'SaaS',
            'frameworkSlug': 'g-cloud-8',
            'serviceName': 'test',
            'supplierId': 1000,
            'id': "1",
            'status': 'published'
        }}
        response = self.client.get('/admin/services/1')
        assert b'Termination cost' not in response.data

        data_api_client.get_service.return_value = {'services': {
            'lot': 'SCS',
            'frameworkSlug': 'g-cloud-8',
            'serviceName': 'test',
            'supplierId': 1000,
            'id': "1",
            'status': 'published'
        }}
        response = self.client.get('/admin/services/1')
        assert b'Termination cost' in response.data

    def test_service_status_update_widgets_not_visible_when_not_permitted(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'lot': 'paas',
            'serviceName': 'test',
            'supplierId': 1000,
            'frameworkSlug': 'g-cloud-8',
            'id': "1",
            'status': 'published'
        }}
        data_api_client.find_audit_events.return_value = self.find_audit_events_api_response
        response = self.client.get('/admin/services/1')
        assert b'Termination cost' in response.data

    def test_view_service_link_appears_for_gcloud_framework(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'lot': 'paas',
            'serviceName': 'test',
            'supplierId': 1000,
            'frameworkSlug': 'g-cloud-8',
            'frameworkFramework': 'g-cloud',
            'id': "1",
            'status': 'published'
        }}
        response = self.client.get('/admin/services/1')
        assert response.status_code == 200

        document = html.fromstring(response.get_data(as_text=True))
        expected_link_text = "View service"
        expected_href = '/g-cloud/services/1'
        expected_link = document.xpath('.//a[contains(@href,"{}")]'.format(expected_href))[0]

        assert expected_link.text == expected_link_text

    def test_view_service_link_does_not_appear_for_dos_framework(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'lot': 'paas',
            'serviceName': 'test',
            'supplierId': 1000,
            'frameworkSlug': 'digital-outcomes-and-specialists-2',
            'frameworkFramework': 'digital-outcomes-and-specialists',
            'id': "1",
            'status': 'published'
        }}
        response = self.client.get('/admin/services/1')
        assert response.status_code == 200

        document = html.fromstring(response.get_data(as_text=True))
        unexpected_href = '/g-cloud/services/1'

        assert not document.xpath('.//a[contains(@href,"{}")]'.format(unexpected_href))

    @pytest.mark.parametrize('url_suffix', ('', '?remove=True'))
    def test_remove_service_link_appears_for_correct_role_and_status(self, data_api_client, url_suffix):
        data_api_client.get_service.return_value = {'services': {
            'lot': 'paas',
            'serviceName': 'test',
            'supplierId': 1000,
            'frameworkSlug': 'digital-outcomes-and-specialists-2',
            'frameworkFramework': 'digital-outcomes-and-specialists',
            'id': "1",
            'status': 'published'
        }}
        response = self.client.get('/admin/services/1{}'.format(url_suffix))
        assert response.status_code == 200

        document = html.fromstring(response.get_data(as_text=True))
        expected_link_text = "Remove service"
        expected_href = '/admin/services/1?remove=True'
        expected_link = document.xpath('.//a[contains(@href,"{}")]'.format(expected_href))[0]

        assert expected_link.text == expected_link_text

    @pytest.mark.parametrize('user_role', ('admin-ccs-sourcing', 'admin-framework-manager', 'admin-manager'))
    def test_no_access_for_certain_roles(self, data_api_client, user_role):
        self.user_role = user_role
        data_api_client.get_service.return_value = {'services': {
            'lot': 'paas',
            'serviceName': 'test',
            'supplierId': 1000,
            'frameworkSlug': 'digital-outcomes-and-specialists-2',
            'frameworkFramework': 'digital-outcomes-and-specialists',
            'id': "1",
            'status': 'published'
        }}
        response = self.client.get('/admin/services/1')
        assert response.status_code == 403

    @pytest.mark.parametrize('service_status', ['disabled', 'enabled'])
    def test_remove_service_does_not_appear_for_certain_statuses(self, data_api_client, service_status):
        data_api_client.get_service.return_value = {'services': {
            'lot': 'paas',
            'serviceName': 'test',
            'supplierId': 1000,
            'frameworkSlug': 'digital-outcomes-and-specialists-2',
            'frameworkFramework': 'digital-outcomes-and-specialists',
            'id': "1",
            'status': service_status
        }}
        data_api_client.find_audit_events.return_value = self.find_audit_events_api_response
        response = self.client.get('/admin/services/1')

        assert response.status_code == 200

        document = html.fromstring(response.get_data(as_text=True))
        unexpected_href = '/admin/services/1?remove=True'
        assert not document.xpath('.//a[contains(@href,"{}")]'.format(unexpected_href))

    def test_publish_service_does_not_appear_for_admin_role(self, data_api_client):
        self.user_role = 'admin'
        data_api_client.get_service.return_value = {'services': {
            'lot': 'paas',
            'serviceName': 'test',
            'supplierId': 1000,
            'frameworkSlug': 'digital-outcomes-and-specialists-2',
            'frameworkFramework': 'digital-outcomes-and-specialists',
            'id': "1",
            'status': 'disabled'
        }}
        data_api_client.find_audit_events.return_value = self.find_audit_events_api_response
        response = self.client.get('/admin/services/1')

        assert response.status_code == 200

        document = html.fromstring(response.get_data(as_text=True))
        unexpected_href = '/admin/services/1?publish=True'
        assert not document.xpath('.//a[contains(@href,"{}")]'.format(unexpected_href))

    def test_remove_service_does_not_appear_for_admin_role(self, data_api_client):
        self.user_role = 'admin'
        data_api_client.get_service.return_value = {'services': {
            'lot': 'paas',
            'serviceName': 'test',
            'supplierId': 1000,
            'frameworkSlug': 'digital-outcomes-and-specialists-2',
            'frameworkFramework': 'digital-outcomes-and-specialists',
            'id': "1",
            'status': 'published'
        }}
        data_api_client.find_audit_events.return_value = self.find_audit_events_api_response
        response = self.client.get('/admin/services/1')

        assert response.status_code == 200

        document = html.fromstring(response.get_data(as_text=True))
        unexpected_href = '/admin/services/1?remove=True'
        assert not document.xpath('.//a[contains(@href,"{}")]'.format(unexpected_href))

    def test_service_view_with_publish_param_shows_publish_banner(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'frameworkSlug': 'g-cloud-8',
            'serviceName': 'test',
            'lot': 'iaas',
            'id': "314159265",
            'supplierId': 1000,
            "status": 'disabled',
        }}
        data_api_client.find_audit_events.return_value = self.find_audit_events_api_response

        response = self.client.get('/admin/services/314159265?publish=True')
        document = html.fromstring(response.get_data(as_text=True))
        banner_text = document.xpath("//div[@class='banner-destructive-with-action']/p")[0].text.strip()
        expected_text = "Are you sure you want to publish ‘test’?"

        assert banner_text == expected_text

    def test_service_view_with_remove_param_shows_remove_banner(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'frameworkSlug': 'g-cloud-8',
            'serviceName': 'test',
            'lot': 'iaas',
            'id': "314159265",
            'supplierId': 1000,
            "status": 'published',
        }}
        data_api_client.find_audit_events.return_value = self.find_audit_events_api_response

        response = self.client.get('/admin/services/314159265?remove=True')
        document = html.fromstring(response.get_data(as_text=True))
        banner_text = document.xpath("//div[@class='banner-destructive-with-action']/p")[0].text.strip()
        expected_text = "Are you sure you want to remove ‘test’?"

        assert banner_text == expected_text


@mock.patch('app.main.views.services.data_api_client', autospec=True)
class TestServiceEdit(LoggedInApplicationTest):
    user_role = 'admin-ccs-category'

    def test_edit_dos_service_title(self, data_api_client):
        service = {
            "id": 123,
            "frameworkSlug": "digital-outcomes-and-specialists",
            "serviceName": "Larry O'Rourke's",
            "supplierId": 1000,
            "lot": "user-research-studios",
        }
        data_api_client.get_service.return_value = {'services': service}
        response = self.client.get('/admin/services/123/edit/description')
        document = html.fromstring(response.get_data(as_text=True))

        data_api_client.get_service.assert_called_with('123')

        assert response.status_code == 200
        assert document.xpath(
            "normalize-space(string(//input[@name='serviceName']/@value))"
        ) == service["serviceName"]
        assert document.xpath(
            "//nav//a[@href='/admin/services/123'][normalize-space(string())=$t]",
            t=service["serviceName"],
        )

    def test_no_link_to_edit_dos2_service_essentials(self, data_api_client):
        service = {
            "id": 123,
            "frameworkSlug": "digital-outcomes-and-specialists-2",
            "serviceName": "Test",
            "supplierId": 1000,
            "lot": "digital-outcomes",
            'status': 'published'
        }
        data_api_client.get_service.return_value = {'services': service}
        data_api_client.find_audit_events.return_value = {'auditEvents': []}

        response = self.client.get('/admin/services/123')
        assert response.status_code == 200

        document = html.fromstring(response.get_data(as_text=True))
        all_links_on_page = [i.values()[0] for i in document.xpath('(//body//a)')]
        assert '/admin/services/123/edit/service-essentials' not in all_links_on_page

    def test_add_link_for_empty_multiquestion(self, data_api_client):
        service = {
            "id": 123,
            "frameworkSlug": "digital-outcomes-and-specialists-2",
            "serviceName": "Test",
            "supplierId": 1000,
            "lot": "digital-outcomes",
            "performanceAnalysisAndData": '',
            'status': 'published'
        }

        data_api_client.get_service.return_value = {'services': service}
        data_api_client.find_audit_events.return_value = {'auditEvents': []}

        response = self.client.get('/admin/services/123')
        assert response.status_code == 200

        document = html.fromstring(response.get_data(as_text=True))
        performance_analysis_and_data_link = "/admin/services/123/edit/team-capabilities/performance-analysis-and-data"
        performance_analysis_and_data_link_text = document.xpath(
            '//a[contains(@href, "{}")]//text()'.format(performance_analysis_and_data_link)
        )[0]
        assert performance_analysis_and_data_link_text == 'Add'

    def test_edit_link_for_populated_multiquestion(self, data_api_client):
        service = {
            "id": 123,
            "frameworkSlug": "digital-outcomes-and-specialists-2",
            "serviceName": "Test",
            "supplierId": 1000,
            "lot": "digital-outcomes",
            "performanceAnalysisTypes": 'some value',
            'status': 'published'
        }

        data_api_client.get_service.return_value = {'services': service}
        data_api_client.find_audit_events.return_value = {'auditEvents': []}

        response = self.client.get('/admin/services/123')
        assert response.status_code == 200

        document = html.fromstring(response.get_data(as_text=True))
        performance_analysis_and_data_link = "/admin/services/123/edit/team-capabilities/performance-analysis-and-data"
        performance_analysis_and_data_link_text = document.xpath(
            '//a[contains(@href, "{}")]//text()'.format(performance_analysis_and_data_link)
        )[0]
        assert performance_analysis_and_data_link_text == 'Edit'

    def test_multiquestion_get_route(self, data_api_client):
        service = {
            "id": 123,
            "frameworkSlug": "digital-outcomes-and-specialists-2",
            "serviceName": "Test",
            "supplierId": 1000,
            "lot": "digital-specialists",
            "performanceAnalysisAndData": '',
        }

        data_api_client.get_service.return_value = {'services': service}
        response = self.client.get('/admin/services/123/edit/individual-specialist-roles/business-analyst')

        assert response.status_code == 200

    def test_service_edit_documents_get_response(self, data_api_client):
        service = {
            "id": 321,
            'frameworkSlug': 'g-cloud-8',
            "serviceName": "Boylan the billsticker",
            "lot": "scs",
            "termsAndConditionsDocumentURL": "http://boylan.example.com/concert-tours",
        }
        data_api_client.get_service.return_value = {'services': service}
        response = self.client.get('/admin/services/321/edit/documents')
        document = html.fromstring(response.get_data(as_text=True))

        data_api_client.get_service.assert_called_with('321')

        assert response.status_code == 200
        assert document.xpath("//input[@name='termsAndConditionsDocumentURL']")  # file inputs are complex, yeah?
        # ensure a field that data doesn't yet exist for is shown
        assert document.xpath("//input[@name='sfiaRateDocumentURL']")
        assert document.xpath(
            "//nav//a[@href='/admin/services/321'][normalize-space(string())=$t]",
            t=service["serviceName"],
        )

    def test_service_edit_with_no_features_or_benefits(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'lot': 'saas',
            'frameworkSlug': 'g-cloud-8',
        }}
        response = self.client.get(
            '/admin/services/234/edit/features-and-benefits')

        data_api_client.get_service.assert_called_with('234')

        assert response.status_code == 200
        assert 'id="input-serviceFeatures-0"class="text-box"value=""' in self.strip_all_whitespace(
            response.get_data(as_text=True)
        )

    def test_service_edit_with_one_service_feature(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'id': 1,
            'supplierId': 2,
            'frameworkSlug': 'g-cloud-8',
            'lot': 'IaaS',
            'serviceFeatures': [
                "bar",
            ],
            'serviceBenefits': [
                "foo",
            ],
        }}
        response = self.client.get(
            '/admin/services/1/edit/features-and-benefits'
        )
        assert response.status_code == 200
        stripped_page = self.strip_all_whitespace(response.get_data(as_text=True))
        assert 'id="input-serviceFeatures-0"class="text-box"value="bar"' in stripped_page
        assert 'id="input-serviceFeatures-1"class="text-box"value=""' in stripped_page

    def test_service_edit_assurance_questions(self, data_api_client):
        service = {
            'frameworkSlug': 'g-cloud-8',
            'lot': 'saas',
            'serviceAvailabilityPercentage': {
                "value": "31.415",
                "assurance": "Contractual commitment",
            },
        }
        data_api_client.get_service.return_value = {'services': service}
        response = self.client.get('/admin/services/432/edit/asset-protection-and-resilience')
        document = html.fromstring(response.get_data(as_text=True))

        data_api_client.get_service.assert_called_with('432')

        assert response.status_code == 200
        assert document.xpath(
            "//input[@name='serviceAvailabilityPercentage']/@value"
        ) == [service["serviceAvailabilityPercentage"]["value"]]
        assert document.xpath(
            "//input[@type='radio'][@name='serviceAvailabilityPercentage--assurance'][@checked]/@value"
        ) == ["Contractual commitment"]
        # ensure a field that data doesn't yet exist for is shown
        assert document.xpath("//input[@name='dataManagementLocations']")
        assert document.xpath("//input[@name='dataManagementLocations--assurance']")

    def test_service_edit_with_no_section_returns_404(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'lot': 'saas',
            'frameworkSlug': 'g-cloud-8',
        }}
        response = self.client.get(
            '/admin/services/234/edit/bad-section')

        data_api_client.get_service.assert_called_with('234')
        assert response.status_code == 404


@mock.patch('app.main.views.services.data_api_client', autospec=True)
class TestServiceUpdate(LoggedInApplicationTest):
    user_role = 'admin-ccs-category'

    @pytest.mark.parametrize("role,expected_code", [
        ("admin", 403),
        ("admin-ccs-category", 302),
        ("admin-ccs-sourcing", 403),
        ("admin-manager", 403),
    ])
    def test_post_service_update_is_only_accessible_to_specific_user_roles(self, data_api_client, role, expected_code):
        self.user_role = role
        data_api_client.get_service.return_value = {'services': {
            'id': 1,
            'supplierId': 2,
            'frameworkSlug': 'g-cloud-8',
            'lot': 'IaaS',
        }}
        response = self.client.post(
            '/admin/services/1/edit/features-and-benefits',
            data={
                'serviceFeatures': 'baz',
                'serviceBenefits': 'foo',
            }
        )
        actual_code = response.status_code
        assert actual_code == expected_code, "Unexpected response {} for role {}".format(actual_code, role)

    def test_service_update_documents_empty_post(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'id': 1,
            'supplierId': 2,
            'frameworkSlug': 'g-cloud-7',
            'lot': 'SCS',
            'serviceDefinitionDocumentURL': '',
            'termsAndConditionsDocumentURL': '',
            'sfiaRateDocumentURL': '',
            'pricingDocumentURL': '',
        }}
        response = self.client.post(
            '/admin/services/1/edit/documents',
            data={}
        )

        data_api_client.get_service.assert_called_with('1')
        assert data_api_client.update_service.call_args_list == []

        assert response.status_code == 302
        assert urlsplit(response.location).path == "/admin/services/1"

    def test_service_update_documents(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'id': 1,
            'supplierId': 2,
            'frameworkSlug': 'g-cloud-7',
            'lot': 'SCS',
            'pricingDocumentURL': "http://assets/documents/1/2-pricing.pdf",
            'serviceDefinitionDocumentURL': "http://assets/documents/1/2-service-definition.pdf",
            'termsAndConditionsDocumentURL': "http://assets/documents/1/2-terms-and-conditions.pdf",
            'sfiaRateDocumentURL': None
        }}
        response = self.client.post(
            '/admin/services/1/edit/documents',
            data={
                'serviceDefinitionDocumentURL': (StringIO(), ''),
                'pricingDocumentURL': (StringIO(b"doc"), 'test.pdf'),
                'sfiaRateDocumentURL': (StringIO(b"doc"), 'test.pdf'),
                'termsAndConditionsDocumentURL': (StringIO(b''), ''),
            }
        )

        data_api_client.get_service.assert_called_with('1')
        data_api_client.update_service.assert_called_with('1', {
            'pricingDocumentURL': 'https://assets.test.digitalmarketplace.service.gov.uk/g-cloud-7/documents/2/1-pricing-document-2015-01-01-1200.pdf',  # noqa
            'sfiaRateDocumentURL': 'https://assets.test.digitalmarketplace.service.gov.uk/g-cloud-7/documents/2/1-sfia-rate-card-2015-01-01-1200.pdf',  # noqa
        }, 'test@example.com', user_role='admin')

        assert response.status_code == 302

    def test_service_update_documents_with_validation_errors(
            self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'id': 7654,
            'supplierId': 2,
            'frameworkSlug': 'g-cloud-7',
            'lot': 'SCS',
            'serviceDefinitionDocumentURL': "http://assets/documents/7654/2-service-definition.pdf",
            'pricingDocumentURL': "http://assets/documents/7654/2-pricing.pdf",
            'sfiaRateDocumentURL': None
        }}
        response = self.client.post(
            '/admin/services/7654/edit/documents',
            data={
                'serviceDefinitionDocumentURL': (StringIO(), ''),
                'pricingDocumentURL': (StringIO(b"doc"), 'test.pdf'),
                'sfiaRateDocumentURL': (StringIO(b"doc"), 'test.txt'),
                'termsAndConditionsDocumentURL': (StringIO(), 'test.pdf'),
            }
        )
        document = html.fromstring(response.get_data(as_text=True))

        data_api_client.get_service.assert_called_with('7654')
        assert data_api_client.update_service.call_args_list == []
        assert response.status_code == 400

        assert document.xpath(
            "//*[contains(@class,'validation-message')][contains(normalize-space(string()), $t)]",
            t="Your document is not in an open format",
        )
        assert document.xpath(
            "//a[normalize-space(string())=$t]/@href",
            t="Return without saving",
        ) == ["/admin/services/7654"]

    def test_service_update_assurance_questions_when_API_returns_error(
            self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'id': "7654",
            'supplierId': 2,
            'frameworkSlug': 'g-cloud-8',
            'lot': 'paas',
        }}
        data_api_client.update_service.side_effect = HTTPError(None, {'dataProtectionWithinService': 'answer_required'})
        posted_values = {
            "dataProtectionBetweenUserAndService": ["PSN assured service"],
            # dataProtectionWithinService deliberately omitted
            "dataProtectionBetweenServices": [
                "TLS (HTTPS or VPN) version 1.2 or later",
                "Legacy SSL or TLS (HTTPS or VPN)",
            ],
        }
        posted_assurances = {
            "dataProtectionBetweenUserAndService--assurance": "Independent testing of implementation",
            "dataProtectionWithinService--assurance": "CESG-assured components",
            "dataProtectionBetweenServices--assurance": "Service provider assertion",
        }

        response = self.client.post(
            "/admin/services/7654/edit/data-in-transit-protection",
            data=dict(posted_values, **posted_assurances),
        )
        document = html.fromstring(response.get_data(as_text=True))

        assert response.status_code == 400
        data_api_client.get_service.assert_called_with('7654')
        assert data_api_client.update_service.call_args_list == [
            mock.call(
                '7654',
                {
                    "dataProtectionBetweenUserAndService": {
                        "value": posted_values["dataProtectionBetweenUserAndService"],
                        "assurance": posted_assurances["dataProtectionBetweenUserAndService--assurance"],
                    },
                    "dataProtectionWithinService": {
                        "assurance": posted_assurances["dataProtectionWithinService--assurance"],
                    },
                    "dataProtectionBetweenServices": {
                        "value": posted_values["dataProtectionBetweenServices"],
                        "assurance": posted_assurances["dataProtectionBetweenServices--assurance"],
                    },
                },
                'test@example.com', user_role='admin')
        ]
        for key, values in posted_values.items():
            assert sorted(document.xpath("//form//input[@type='checkbox'][@name=$n][@checked]/@value", n=key)) == \
                sorted(values)

        for key, value in posted_assurances.items():
            assert sorted(document.xpath("//form//input[@type='radio'][@name=$n][@checked]/@value", n=key)) == \
                [value]

        assert document.xpath(
            "//*[contains(@class,'validation-message')][contains(normalize-space(string()), $t)]",
            t="You need to answer this question",
        )
        assert document.xpath(
            "//a[normalize-space(string())=$t]/@href",
            t="Return without saving",
        ) == ["/admin/services/7654"]

    def test_service_update_with_one_service_feature(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'id': 1,
            'supplierId': 2,
            'frameworkSlug': 'g-cloud-8',
            'lot': 'IaaS',
            'serviceFeatures': [
                "bar",
            ],
            'serviceBenefits': [
                "foo",
            ],
        }}
        response = self.client.post(
            '/admin/services/1/edit/features-and-benefits',
            data={
                'serviceFeatures': 'baz',
                'serviceBenefits': 'foo',
            }
        )

        assert data_api_client.update_service.call_args_list == [
            mock.call(
                '1',
                {'serviceFeatures': ['baz'], 'serviceBenefits': ['foo']},
                'test@example.com',
                user_role='admin'
            )]
        assert response.status_code == 302

    def test_service_update_multiquestion_post_route(self, data_api_client):
        service = {
            "id": 123,
            "frameworkSlug": "digital-outcomes-and-specialists-2",
            "serviceName": "Test",
            "lot": "digital-specialists",
            "businessAnalyst": '',
        }
        data_api_client.get_service.return_value = {'services': service}

        data = {
            'businessAnalystLocations': ["London", "Offsite", "Scotland", "Wales"],
            'businessAnalystPriceMin': '100',
            'businessAnalystPriceMax': '150',
        }
        response = self.client.post(
            '/admin/services/123/edit/individual-specialist-roles/business-analyst',
            data=data
        )

        assert response.status_code == 302
        assert data_api_client.update_service.call_args_list == [
            mock.call('123', data, 'test@example.com', user_role='admin')
        ]

    def test_service_update_with_multiquestion_validation_error(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'id': 1,
            'supplierId': 2,
            'frameworkSlug': 'g-cloud-9',
            'lot': 'cloud-hosting',
            'serviceFeatures': [
                "bar",
            ],
            'serviceBenefits': [
                "foo",
            ],
        }}
        mock_api_error = mock.Mock(status_code=400)
        mock_api_error.json.return_value = {
            "error": {"serviceBenefits": "under_10_words", "serviceFeatures": "under_10_words"}
        }
        data_api_client.update_service.side_effect = HTTPError(mock_api_error)

        response = self.client.post(
            '/admin/services/1/edit/service-features-and-benefits',
            data={
                'serviceFeatures': 'one 2 three 4 five 6 seven 8 nine 10 eleven',
                'serviceBenefits': '11 10 9 8 7 6 5 4 3 2 1',
            },
            follow_redirects=True
        )

        assert response.status_code == 400
        assert data_api_client.update_service.call_args_list == [
            mock.call(
                '1',
                {'serviceFeatures': ['one 2 three 4 five 6 seven 8 nine 10 eleven'],
                 'serviceBenefits': ['11 10 9 8 7 6 5 4 3 2 1']},
                'test@example.com', user_role='admin')
        ]

        document = html.fromstring(response.get_data(as_text=True))

        validation_banner_h1 = document.xpath("//h1[@class='validation-masthead-heading']//text()")[0].strip()
        assert validation_banner_h1 == "There was a problem with your answer to:"

        validation_banner_links = [
            (anchor.text_content(), anchor.get('href')) for anchor in
            document.xpath("//a[@class='validation-masthead-link']")
        ]
        assert validation_banner_links == [
            ("Service benefits", "#serviceBenefits"),
            ("Service features", "#serviceFeatures")
        ]

        validation_errors = [error.strip() for error in document.xpath("//span[@class='validation-message']//text()")]
        assert validation_errors == [
            "You can’t write more than 10 words for each feature.",
            "You can’t write more than 10 words for each benefit."
        ]

    def test_service_update_with_assurance_questions(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'id': 567,
            'supplierId': 987,
            'frameworkSlug': 'g-cloud-8',
            'lot': 'IaaS',
            'onboardingGuidance': {
                "value": False,
                "assurance": "Independent validation of assertion",
            },
            'interconnectionMethods': {
                "value": ["PSN assured service", "Private WAN"],
                "assurance": "Service provider assertion",
            },
        }}
        response = self.client.post(
            '/admin/services/567/edit/external-interface-protection',
            data={
                'onboardingGuidance': 'false',
                'onboardingGuidance--assurance': "Service provider assertion",
                'interconnectionMethods': ["Private WAN"],
                'interconnectionMethods--assurance': "Service provider assertion",
            },
        )
        assert data_api_client.update_service.call_args_list == [
            mock.call(
                '567',
                {
                    'onboardingGuidance': {
                        "value": False,
                        "assurance": "Service provider assertion",
                    },
                    'interconnectionMethods': {
                        "value": ["Private WAN"],
                        "assurance": "Service provider assertion",
                    },
                },
                'test@example.com', user_role='admin')
        ]
        assert response.status_code == 302

    @mock.patch('app.main.views.services.upload_service_documents')
    def test_service_update_when_API_returns_error(self, upload_service_documents, data_api_client):
        assert isinstance(s3.S3, mock.Mock)

        data_api_client.get_service.return_value = {'services': {
            'id': 1,
            'supplierId': 2,
            'lot': 'SCS',
            'frameworkSlug': 'g-cloud-7',
            'pricingDocumentURL': "http://assets/documents/1/2-pricing.pdf",
            'sfiaRateDocumentURL': None
        }}
        upload_service_documents.return_value = ({}, {})
        data_api_client.update_service.side_effect = HTTPError(None, {'sfiaRateDocumentURL': 'required'})

        response = self.client.post(
            '/admin/services/1/edit/documents',
            data={
                'pricingDocumentURL': (StringIO(b"doc"), 'test.pdf'),
                'sfiaRateDocumentURL': (StringIO(b"doc"), 'test.txt'),
                'termsAndConditionsDocumentURL': (StringIO(), 'test.pdf'),
            }
        )
        assert 'There was a problem with the answer to this question' in response.get_data(as_text=True)

    def test_service_update_with_no_service_returns_404(self, data_api_client):
        data_api_client.get_service.return_value = None
        response = self.client.post(
            '/admin/services/234/edit/documents',
            data={
                'pricingDocumentURL': (StringIO(b"doc"), 'test.pdf'),
                'sfiaRateDocumentURL': (StringIO(b"doc"), 'test.txt'),
                'termsAndConditionsDocumentURL': (StringIO(), 'test.pdf'),
            }
        )

        data_api_client.get_service.assert_called_with('234')
        assert response.status_code == 404

    @pytest.mark.parametrize('framework_slug', ('g-cloud-7', 'digital-outcomes-and-specialists-2'))
    def test_service_update_with_no_section_returns_404(self, data_api_client, framework_slug):
        data_api_client.get_service.return_value = {'services': {
            'id': 1,
            'serviceName': 'test',
            'supplierId': 2,
            'lot': 'SCS',
            'frameworkSlug': framework_slug,
            'pricingDocumentURL': "http://assets/documents/1/2-pricing.pdf",
            'sfiaRateDocumentURL': None
        }}
        response = self.client.post(
            '/admin/services/234/edit/bad-section',
            data={
                'pricingDocumentURL': (StringIO(b"doc"), 'test.pdf'),
                'sfiaRateDocumentURL': (StringIO(b"doc"), 'test.txt'),
                'termsAndConditionsDocumentURL': (StringIO(), 'test.pdf'),
            }
        )

        data_api_client.get_service.assert_called_with('234')
        assert response.status_code == 404


@mock.patch('app.main.views.services.data_api_client', autospec=True)
class TestServiceStatusUpdate(LoggedInApplicationTest):
    user_role = 'admin-ccs-category'

    @pytest.mark.parametrize("role,expected_code", [
        ("admin", 403),
        ("admin-ccs-category", 302),
        ("admin-ccs-sourcing", 403),
        ("admin-manager", 403),
    ])
    def test_post_status_update_is_only_accessible_to_specific_user_roles(self, data_api_client, role, expected_code):
        self.user_role = role
        data_api_client.get_service.return_value = {'services': {
            'frameworkSlug': 'g-cloud-9',
            'serviceName': 'bad service',
            'supplierId': 1000,
            'status': 'published',
        }}
        data_api_client.find_audit_events.return_value = {'auditEvents': []}
        response = self.client.post('/admin/services/status/1',
                                    data={'service_status': 'removed'})
        actual_code = response.status_code

        assert actual_code == expected_code, "Unexpected response {} for role {}".format(actual_code, role)

    def test_status_update_to_removed(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'frameworkSlug': 'g-cloud-7',
            'serviceName': 'test',
            'supplierId': 1000,
            'status': 'published',
        }}
        data_api_client.find_audit_events.return_value = {'auditEvents': []}
        response = self.client.post('/admin/services/status/1', data={'service_status': 'removed'})
        data_api_client.update_service_status.assert_called_with('1', 'disabled', 'test@example.com')

        assert response.status_code == 302
        assert response.location == 'http://localhost/admin/services/1'
        assert_flashes(self, 'status_updated')

    def test_cannot_update_status_to_private(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'frameworkSlug': 'g-cloud-8',
            'serviceName': 'test',
            'supplierId': 1000,
            'status': 'published',
        }}
        data_api_client.find_audit_events.return_value = {'auditEvents': []}
        response = self.client.post('/admin/services/status/1', data={'service_status': 'private'})

        assert not data_api_client.update_service_status.called
        assert response.status_code == 302
        assert response.location == 'http://localhost/admin/services/1'
        assert_flashes(self, 'bad_status', 'error')

    def test_status_update_to_published(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'frameworkSlug': 'digital-outcomes-and-specialists',
            'serviceName': 'test',
            'supplierId': 1000,
            'status': 'enabled',
        }}

        data_api_client.find_audit_events.return_value = {'auditEvents': []}
        response = self.client.post('/admin/services/status/1', data={'service_status': 'public'})
        data_api_client.update_service_status.assert_called_with('1', 'published', 'test@example.com')

        assert response.status_code == 302
        assert response.location == 'http://localhost/admin/services/1'
        assert_flashes(self, 'status_updated')

    def test_bad_status_gives_error_message(self, data_api_client):
        data_api_client.get_service.return_value = {'services': {
            'frameworkSlug': 'g-cloud-7',
            'serviceName': 'test',
            'supplierId': 1000,
            'status': 'published',
        }}
        data_api_client.find_audit_events.return_value = {'auditEvents': []}
        response = self.client.post('/admin/services/status/1', data={'service_status': 'suspended'})

        assert response.status_code == 302
        assert response.location == 'http://localhost/admin/services/1'
        assert_flashes(self, 'bad_status', 'error')

    def test_services_with_missing_id(self, data_api_client):
        response = self.client.get('/admin/services')

        assert response.status_code == 404


@mock.patch("app.main.views.services.html_diff_tables_from_sections_iter", autospec=True)
@mock.patch('app.main.views.services.data_api_client', autospec=True)
class TestServiceUpdates(LoggedInApplicationTest):
    @pytest.mark.parametrize("role,expected_code", [
        ("admin", 403),
        ("admin-ccs-category", 200),
        ("admin-ccs-sourcing", 403),
        ("admin-manager", 403),
    ])
    def test_view_service_updates_is_only_accessible_to_specific_user_roles(
            self, data_api_client, html_diff_tables_from_sections_iter, role, expected_code
    ):
        self.user_role = role
        data_api_client.get_service.return_value = self._mock_get_service_side_effect("published", "151")
        response = self.client.get('/admin/services/31415/updates')
        actual_code = response.status_code
        assert actual_code == expected_code, "Unexpected response {} for role {}".format(actual_code, role)

    def test_nonexistent_service(self, data_api_client, html_diff_tables_from_sections_iter):
        self.user_role = 'admin-ccs-category'
        data_api_client.get_service.return_value = None
        response = self.client.get('/admin/services/31415/updates')
        assert response.status_code == 404
        assert data_api_client.get_service.call_args_list == [(("31415",), {},)]

    @staticmethod
    def _mock_get_service_side_effect(status, service_id):
        return {"services": {
            "151": {
                "id": "151",
                "frameworkSlug": "g-cloud-9",
                "lot": "cloud-hosting",
                "status": status,
                "supplierId": 909090,
                "supplierName": "Barrington's",
                "serviceName": "Lemonflavoured soap",
            },
        }[service_id]}

    @staticmethod
    def _mock_get_archived_service_side_effect(old_versions_of_services, archived_service_id):
        return {"services": old_versions_of_services[archived_service_id]}

    @staticmethod
    def _mock_get_supplier_side_effect(supplier_id):
        return {"suppliers": {
            909090: {
                "id": 909090,
                "name": "Barrington's",
                "contactInformation": [
                    {
                        "email": "sir.jonah.barrington@example.com",
                    },
                ],
            },
        }[supplier_id]}

    @staticmethod
    def _mock_find_audit_events_side_effect(find_audit_events_api_response, implicit_page_len, **kwargs):
        if kwargs.get("page") or kwargs.get("page_len"):
            raise NotImplementedError

        links = {
            "self": "http://example.com/dummy",
        }
        if len(find_audit_events_api_response) > implicit_page_len:
            links["next"] = "http://example.com/dummy_next"
        if kwargs.get("latest_first") == "true":
            find_audit_events_api_response = find_audit_events_api_response[::-1]
        return {
            "auditEvents": find_audit_events_api_response[:implicit_page_len],
            "links": links,
        }

    _service_status_labels = {
        "disabled": "Removed",
        "enabled": "Private",
        "published": "Public",
    }

    expected_message_about_latest_edit_1 = "someone@example.com made 1 edit on Wednesday 3 February 2010."
    disabled_service_one_edit = (
        # find_audit_events api response:
        [
            {
                "id": 567567,
                "type": "update_service",
                "acknowledged": False,
                "data": {
                    "oldArchivedServiceId": "789",
                    "newArchivedServiceId": "678",
                },
                "createdAt": "2010-02-03T10:11:12.345Z",
                "user": "someone@example.com",
            }
        ],
        # old versions of edited services:
        {
            "789": {
                "frameworkSlug": "g-cloud-9",
                "lot": "cloud-hosting",
                "supplierId": 909090,
                "supplierName": "Barrington's",
                "serviceName": "Melonflavoured soap",
            },
        },
        # service status:
        "disabled",
        # expected message about the oldest unapproved edit:
        "Changed on Wednesday 3 February 2010 at 10:11am",
        # number of audit events per page in API response + expected message about latest edit:
        ((5, expected_message_about_latest_edit_1,),),
    )

    expected_message_about_latest_edit_2 = "More than one user has edited this service. " \
        "The last user to edit this service was florrie@example.com on Sunday 22 March 2015."
    published_service_multiple_edits = (
        # find_audit_events api response:
        (
            {
                "id": 1928374,
                "type": "update_service",
                "acknowledged": False,
                "data": {
                    "oldArchivedServiceId": "111",
                    "newArchivedServiceId": "222",
                },
                "createdAt": "2015-02-03T20:11:12.345Z",
                "user": "lynch@example.com",
            },
            {
                "id": 293847,
                "type": "update_service",
                "acknowledged": False,
                "data": {
                    "oldArchivedServiceId": "222",
                    "newArchivedServiceId": "333",
                },
                "createdAt": "2015-03-22T12:55:12.345Z",
                "user": "lynch@example.com",
            },
            {
                "id": 948576,
                "type": "update_service",
                "acknowledged": False,
                "data": {
                    "oldArchivedServiceId": "333",
                    "newArchivedServiceId": "444",
                },
                "createdAt": "2015-03-22T12:57:12.345Z",
                "user": "florrie@example.com",
            },
        ),
        # old versions of edited services:
        {
            "111": {
                "frameworkSlug": "g-cloud-9",
                "lot": "cloud-hosting",
                "supplierId": 909090,
                "supplierName": "Mr Lambe from London",
                "serviceName": "Lamb of London, who takest away the sins of our world.",
                "somethingIrrelevant": "Soiled personal linen, wrong side up with care.",
            },
        },
        # service status:
        "published",
        # expected message about the oldest unapproved edit:
        "Changed on Tuesday 3 February 2015 at 8:11pm",
        # number of audit events per page in API response + expected message about latest edit:
        (
            (5, expected_message_about_latest_edit_2),
            (2, expected_message_about_latest_edit_2),
            (1, expected_message_about_latest_edit_2)
        )
    )

    expected_message_about_latest_edit_3 = "marion@example.com made 2 edits on Saturday 30 June 2012."
    enabled_service_multiple_edits_by_same_user = (
        # find_audit_events api response:
        (
            {
                "id": 65432,
                "type": "update_service",
                "acknowledged": False,
                "data": {
                    "oldArchivedServiceId": "4444",
                    "newArchivedServiceId": "5555",
                },
                "createdAt": "2012-06-30T20:01:12.345Z",
                "user": "marion@example.com",
            },
            {
                "id": 76543,
                "type": "update_service",
                "acknowledged": False,
                "data": {
                    "oldArchivedServiceId": "5555",
                    "newArchivedServiceId": "6666",
                },
                "createdAt": "2012-06-30T22:55:12.345Z",
                "user": "marion@example.com",
            },
        ),
        # old versions of edited services:
        {
            "4444": {
                "id": "151",
                "frameworkSlug": "g-cloud-9",
                "lot": "cloud-hosting",
                "supplierId": 909090,
                "supplierName": "Barrington's",
                "serviceName": "Lemonflavoured soap",
            },
        },
        # service status:
        "enabled",
        # expected message about the oldest unapproved edit:
        "Changed on Saturday 30 June 2012 at 9:01pm",
        # number of audit events per page in API response + expected message about latest edit:
        (
            (5, expected_message_about_latest_edit_3),
            (2, expected_message_about_latest_edit_3),
            (1, expected_message_about_latest_edit_3)
        )
    )

    expected_message_about_latest_edit_4 = "More than one user has edited this service. " \
        "The last user to edit this service was private.carr@example.com on Saturday 17 December 2005."
    enabled_service_with_multiple_user_edits = (
        # find_audit_events api response:
        (
            {
                "id": 556677,
                "type": "update_service",
                "acknowledged": False,
                "data": {
                    "oldArchivedServiceId": "3535",
                    "newArchivedServiceId": "6767",
                },
                "createdAt": "2005-11-12T15:01:12.345Z",
                "user": "private.carr@example.com",
            },
            {
                "id": 668833,
                "type": "update_service",
                "acknowledged": False,
                "data": {
                    "oldArchivedServiceId": "6767",
                    "newArchivedServiceId": "7373",
                },
                "createdAt": "2005-12-10T11:55:12.345Z",
                "user": "private.carr@example.com",
            },
            {
                "id": 449966,
                "type": "update_service",
                "acknowledged": False,
                "data": {
                    "oldArchivedServiceId": "7373",
                    "newArchivedServiceId": "4747",
                },
                "createdAt": "2005-12-11T12:55:12.345Z",
                "user": "cissy@example.com",
            },
            {
                "id": 221188,
                "type": "update_service",
                "acknowledged": False,
                "data": {
                    "oldArchivedServiceId": "4747",
                    "newArchivedServiceId": "9292",
                },
                "createdAt": "2005-12-17T09:22:12.345Z",
                "user": "private.carr@example.com",
            },
        ),
        # old versions of edited services:
        {
            "3535": {
                "id": "151",
                "frameworkSlug": "g-cloud-9",
                "lot": "cloud-hosting",
                "supplierId": 909090,
                "supplierName": "Barrington's",
                "serviceName": "Lemonflavoured soup",
            },
        },
        # service status:
        "enabled",
        # expected message about the oldest unapproved edit:
        "Changed on Saturday 12 November 2005 at 3:01pm",
        # number of audit events per page in API response + expected message about latest edit:
        (
            (5, expected_message_about_latest_edit_4),
            (3, expected_message_about_latest_edit_4),
            (2, expected_message_about_latest_edit_4)
        )
    )

    enabled_service_with_no_edits = (
        (),
        {},
        "enabled",
        None,
        ((5, "This service has no unapproved edits.",),)
    )

    @pytest.mark.parametrize(
        "find_audit_events_api_response,old_versions_of_services,service_status,"
        "expected_oldest_edit_info,find_audit_events_page_length",
        chain.from_iterable(
            (
                (fae_api_response, old_vers_of_services, service_status, expected_oldest_edit_info, fae_page_length)
                for fae_page_length, expected_message_about_latest_edit in variant_params
            )
            for fae_api_response, old_vers_of_services, service_status, expected_oldest_edit_info, variant_params in (
                disabled_service_one_edit,
                published_service_multiple_edits,
                enabled_service_multiple_edits_by_same_user,
                enabled_service_with_multiple_user_edits,
                enabled_service_with_no_edits,
            )
        )
    )
    @pytest.mark.parametrize("resultant_diff", (False, True))
    def test_unacknowledged_updates(
        self,
        data_api_client,
        html_diff_tables_from_sections_iter,
        find_audit_events_api_response,
        old_versions_of_services,
        service_status,
        expected_oldest_edit_info,
        find_audit_events_page_length,
        resultant_diff,
    ):
        data_api_client.get_service.side_effect = partial(self._mock_get_service_side_effect, service_status)
        data_api_client.find_audit_events.side_effect = partial(
            self._mock_find_audit_events_side_effect,
            find_audit_events_api_response,
            find_audit_events_page_length,
        )
        data_api_client.get_archived_service.side_effect = partial(
            self._mock_get_archived_service_side_effect,
            old_versions_of_services,
        )
        data_api_client.get_supplier.side_effect = self._mock_get_supplier_side_effect
        html_diff_tables_from_sections_iter.side_effect = lambda *a, **ka: iter((
            ("dummy_section", "dummy_question", Markup("<div class='dummy-diff-table'>dummy</div>")),
        ) if resultant_diff else ())

        self.user_role = "admin-ccs-category"
        response = self.client.get('/admin/services/151/updates')

        assert response.status_code == 200
        doc = html.fromstring(response.get_data(as_text=True))

        assert all(
            kwargs == {
                "object_id": "151",
                "object_type": "services",
                "audit_type": AuditTypes.update_service,
                "acknowledged": "false",
                "latest_first": mock.ANY,
            } for args, kwargs in data_api_client.find_audit_events.call_args_list
        )

        assert doc.xpath("normalize-space(string(//header//*[@class='context']))") == "Barrington's"
        assert doc.xpath("normalize-space(string(//header//h1))") == "Lemonflavoured soap"

        assert len(doc.xpath(
            "//*[@class='dummy-diff-table']"
        )) == (1 if find_audit_events_api_response and resultant_diff else 0)
        assert len(doc.xpath(
            # an element that has the textual contents $reverted_text but doesn't have any children that have *exactly*
            # that text (this stops us getting multiple results for a single appearance of the text, because it includes
            # some of that element's parents - this should therefore select the bottom-most element that completely
            # contains the target text)
            "//*[normalize-space(string())=$reverted_text][not(.//*[normalize-space(string())=$reverted_text])]",
            reverted_text="All changes were reversed.",
        )) == (1 if find_audit_events_api_response and not resultant_diff else 0)

        if find_audit_events_api_response:
            assert html_diff_tables_from_sections_iter.call_args_list == [
                ((), {
                    "sections": mock.ANY,  # test separately later?
                    "revision_1":
                        old_versions_of_services[find_audit_events_api_response[0]["data"]["oldArchivedServiceId"]],
                    "revision_2": self._mock_get_service_side_effect(service_status, "151")["services"],
                    "table_preamble_template": "diff_table/_table_preamble.html",
                },),
            ]

            # in this case we want a strict assertion that *all* of the following are true about the ack_form
            ack_forms = doc.xpath(
                "//form[.//input[@type='submit' and @value=$ack_text]]",
                ack_text="Approve edit{}".format("" if len(find_audit_events_api_response) == 1 else "s"),
            )
            assert len(ack_forms) == 1
            assert ack_forms[0].method == "POST"
            assert ack_forms[0].action == "/admin/services/151/updates/{}/approve".format(
                text_type(find_audit_events_api_response[-1]["id"])
            )
            assert sorted(ack_forms[0].form_values()) == [
                ("csrf_token", mock.ANY),
            ]

            assert bool(doc.xpath(
                "normalize-space(string(//h3[normalize-space(string())=$oldver_title]/ancestor::" +
                "*[contains(@class, 'column')][1]))",
                oldver_title="Previously approved version",
            ) == "Previously approved version " + expected_oldest_edit_info) == bool(resultant_diff)
        else:
            # in this case we want a loose assertion that nothing exists that has anything like any of these properties
            assert not doc.xpath(
                "//form[.//button[@type='submit'][contains(normalize-space(string()), $ack_text)]]",
                ack_text="Approve edit",
            )
            assert not any(form.action.endswith("approve") for form in doc.xpath("//form"))

            assert not doc.xpath(
                "//h3[normalize-space(string())=$oldver_title]",
                oldver_title="Previously approved version",
            )

        assert doc.xpath(
            "//*[.//h4[normalize-space(string())=$title]][normalize-space(string())=$full]" +
            "[.//a[@href=$mailto][normalize-space(string())=$email]]",
            title="Contact supplier:",
            full="Contact supplier: sir.jonah.barrington@example.com",
            mailto="mailto:sir.jonah.barrington@example.com",
            email="sir.jonah.barrington@example.com",
        )

    @pytest.mark.parametrize(
        "find_audit_events_api_response,old_versions_of_services,service_status,"
        "find_audit_events_page_length,expected_latest_edit_info",
        chain.from_iterable(
            (
                (
                    fae_api_response,
                    old_vers_of_services,
                    service_status,
                    find_audit_events_page_length,
                    expected_message_about_latest_edit,
                )
                for find_audit_events_page_length, expected_message_about_latest_edit in variant_params
            )
            for fae_api_response, old_vers_of_services, service_status, expected_oldest_edit_info, variant_params in (
                disabled_service_one_edit,
                published_service_multiple_edits,
                enabled_service_multiple_edits_by_same_user,
                enabled_service_with_multiple_user_edits,
                enabled_service_with_no_edits,
            )
        )
    )
    def test_service_edit_page_displays_last_user_to_edit_a_service(
        self,
        data_api_client,
        html_diff_tables_from_sections_iter,
        find_audit_events_api_response,
        old_versions_of_services,
        service_status,
        find_audit_events_page_length,
        expected_latest_edit_info,
    ):
        data_api_client.get_service.side_effect = partial(self._mock_get_service_side_effect, service_status)
        data_api_client.find_audit_events.side_effect = partial(
            self._mock_find_audit_events_side_effect,
            find_audit_events_api_response,
            find_audit_events_page_length,
        )
        data_api_client.get_archived_service.side_effect = partial(
            self._mock_get_archived_service_side_effect,
            old_versions_of_services,
        )
        data_api_client.get_supplier.side_effect = self._mock_get_supplier_side_effect

        self.user_role = "admin-ccs-category"
        response = self.client.get('/admin/services/151/updates')

        assert response.status_code == 200
        doc = html.fromstring(response.get_data(as_text=True))

        assert doc.xpath("//p[normalize-space(string())=$expected_text]", expected_text=expected_latest_edit_info)
