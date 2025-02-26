# Copyright 2017 Eficent Business and IT Consulting Services S.L.
#   (http://www.eficent.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from unittest import mock
from unittest.mock import patch

from markupsafe import Markup

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountInvoiceMerge(AccountTestInvoicingCommon):
    """
    Tests for Account Invoice Merge.
    """

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.company = cls.company_data_2["company"]
        invoice_date = fields.Date.today()
        cls.invoice1 = cls.init_invoice(
            "out_invoice",
            partner=cls.partner_a,
            invoice_date=invoice_date,
            products=cls.product_a,
        )
        cls.now = cls.invoice1.create_date
        cls.invoice2 = cls.init_invoice(
            "out_invoice",
            partner=cls.partner_a,
            invoice_date=invoice_date,
            products=cls.product_a,
        )
        cls.invoice3 = cls.init_invoice(
            "out_invoice",
            partner=cls.partner_b,
            invoice_date=invoice_date,
            products=cls.product_a,
        )
        cls.invoice4 = cls.init_invoice(
            "in_invoice",
            partner=cls.partner_a,
            invoice_date=invoice_date,
            products=cls.product_a,
        )
        cls.invoice5 = cls.init_invoice(
            "out_invoice",
            partner=cls.partner_a,
            invoice_date=invoice_date,
            products=cls.product_a,
        )
        cls.invoice6 = cls.init_invoice(
            "out_invoice",
            partner=cls.partner_a,
            products=cls.product_a,
            invoice_date=invoice_date,
            company=cls.company,
        )

        cls.inv_model = cls.env["account.move"]
        cls.wiz = cls.env["invoice.merge"]

    def _get_wizard(self, active_ids, create=False):
        wiz = self.wiz.with_context(
            active_ids=active_ids,
            active_model="account.move",
        )
        if create:
            wiz = wiz.create({})
        return wiz

    def _create_invoice(self, partner, name, journal=False, move_type=False):
        if not journal:
            journal = self.env["account.journal"].search(
                [("type", "=", "sale")], limit=1
            )
        if not move_type:
            move_type = "out_invoice"
        invoice = self.inv_model.create(
            {
                "partner_id": partner.id,
                "name": name,
                "move_type": move_type,
                "journal_id": journal.id,
            }
        )
        return invoice

    def test_invoice_merge(self):
        self.assertEqual(len(self.invoice1.invoice_line_ids), 1)
        self.assertEqual(len(self.invoice2.invoice_line_ids), 1)
        invoice_len_args = [
            ("create_date", ">=", self.now),
            ("partner_id", "=", self.partner_a.id),
            ("state", "=", "draft"),
        ]
        start_inv = self.inv_model.search(invoice_len_args)
        self.assertEqual(len(start_inv), 5)

        wiz = self._get_wizard([self.invoice1.id, self.invoice2.id], create=True)
        action = wiz.merge_invoices()

        self.assertLessEqual(
            {
                "type": "ir.actions.act_window",
                "binding_view_types": "list,form",
                "xml_id": "account.action_move_out_invoice_type",
            }.items(),
            action.items(),
            "There was an error and the two invoices were not merged.",
        )

        end_inv = self.inv_model.search(invoice_len_args)
        self.assertEqual(len(end_inv), 4)
        self.assertEqual(len(end_inv[0].invoice_line_ids), 1)
        self.assertEqual(end_inv[0].invoice_line_ids[0].quantity, 2.0)

    def test_error_check(self):
        """Check"""
        # Different partner
        wiz = self._get_wizard([self.invoice1.id, self.invoice3.id], create=True)
        self.assertEqual(
            wiz.error_message, "All invoices must have the same: \n- Partner"
        )

        # Check with only one invoice
        wiz = self._get_wizard([self.invoice1.id], create=True)
        self.assertEqual(
            wiz.error_message,
            "Please select multiple invoices to merge in the list view.",
        )

        # Check with two different invoice type
        wiz = self._get_wizard([self.invoice1.id, self.invoice4.id], create=True)
        self.assertEqual(
            wiz.error_message, "All invoices must have the same: \n- Type\n- Journal"
        )

        # Check with a canceled invoice
        self.invoice5.button_cancel()
        wiz = self._get_wizard([self.invoice1.id, self.invoice5.id], create=True)
        self.assertEqual(
            wiz.error_message,
            "All invoices must have the same: \n- Merge-able State (ex : Draft)",
        )

        # Check with another company
        wiz = self._get_wizard([self.invoice1.id, self.invoice6.id], create=True)
        self.assertEqual(
            wiz.error_message, "All invoices must have the same: \n- Journal\n- Company"
        )

    def test_callback_different_sale_order_00(self):
        if "sale.order" not in self.env.registry:
            return True
        product_1, product_2 = self.env["product.product"].create(
            [
                {
                    "name": "product 1",
                    "list_price": 5.0,
                },
                {
                    "name": "product 2",
                    "list_price": 10.0,
                },
            ]
        )
        # Test pre-computes of lines with order
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    Command.create(
                        {
                            "display_type": "line_section",
                            "name": "Dummy section",
                        }
                    ),
                    Command.create(
                        {
                            "display_type": "line_section",
                            "name": "Dummy section",
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product_1.id,
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product_2.id,
                        }
                    ),
                ],
            }
        )
        sale_order_2 = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    Command.create(
                        {
                            "display_type": "line_section",
                            "name": "Dummy section",
                        }
                    ),
                    Command.create(
                        {
                            "display_type": "line_section",
                            "name": "Dummy section",
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product_1.id,
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product_2.id,
                        }
                    ),
                ],
            }
        )
        sale_order.action_confirm()
        sale_order._create_invoices(final=True)
        sale_order_2.action_confirm()
        sale_order_2._create_invoices(final=True)
        invoices = (sale_order | sale_order_2).mapped(
            "order_line.invoice_lines.move_id"
        )
        invoices_info = invoices.do_merge(
            keep_references=False, date_invoice=fields.Date.today()
        )
        invoices_2 = (sale_order | sale_order_2).mapped(
            "order_line.invoice_lines.move_id"
        )
        invoices_2 = invoices_2.filtered(lambda i: i.state == "draft")
        self.assertEqual(sorted(invoices_2.ids), sorted(list(invoices_info.keys())))

    def _add_qty_delivered_and_create_invoice(self, sale_order):
        for line in sale_order.order_line:
            if line.qty_delivered < line.product_uom_qty:
                line.qty_delivered += 1
        sale_order._create_invoices(final=True)

    def _add_qty_received_and_create_invoice(self, purchase_order):
        for line in purchase_order.order_line:
            if line.qty_received < line.product_qty:
                line.qty_received += 1
        purchase_order.action_create_invoice()

    def test_callback_different_sale_order_01(self):
        if "sale.order" not in self.env.registry:
            return True
        product_1, product_2 = self.env["product.product"].create(
            [
                {"name": "product 1", "list_price": 5.0, "invoice_policy": "delivery"},
                {"name": "product 2", "list_price": 10.0, "invoice_policy": "delivery"},
            ]
        )
        # Test pre-computes of lines with order
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    Command.create({"product_id": product_1.id, "product_uom_qty": 5}),
                    Command.create({"product_id": product_2.id, "product_uom_qty": 5}),
                ],
            }
        )
        sale_order_2 = sale_order.copy()

        sale_order.action_confirm()
        sale_order_2.action_confirm()

        self._add_qty_delivered_and_create_invoice(sale_order)
        self._add_qty_delivered_and_create_invoice(sale_order)
        self._add_qty_delivered_and_create_invoice(sale_order)
        self._add_qty_delivered_and_create_invoice(sale_order_2)
        self._add_qty_delivered_and_create_invoice(sale_order_2)
        self._add_qty_delivered_and_create_invoice(sale_order_2)

        inv_sale_order = sale_order.mapped("order_line.invoice_lines.move_id")
        inv_sale_order_2 = sale_order_2.mapped("order_line.invoice_lines.move_id")
        total_inv_sale_order = inv_sale_order | inv_sale_order_2

        self.assertEqual(len(inv_sale_order), 3)
        self.assertEqual(len(inv_sale_order_2), 3)
        self.assertEqual(len(total_inv_sale_order), 6)
        for line in sale_order.order_line:
            self.assertEqual(line.qty_delivered, 3)
            self.assertEqual(line.qty_invoiced, 3)
        for line in sale_order_2.order_line:
            self.assertEqual(line.qty_delivered, 3)
            self.assertEqual(line.qty_invoiced, 3)

        invoices = (
            sale_order.mapped("order_line.invoice_lines.move_id")[:1]
            | sale_order_2.mapped("order_line.invoice_lines.move_id")[:1]
        )
        invoices.do_merge(keep_references=False, date_invoice=fields.Date.today())

        inv_sale_order = sale_order.mapped("order_line.invoice_lines.move_id")
        inv_sale_order_2 = sale_order_2.mapped("order_line.invoice_lines.move_id")
        total_inv_sale_order = inv_sale_order | inv_sale_order_2

        self.assertEqual(len(inv_sale_order), 3)
        self.assertEqual(len(inv_sale_order_2), 3)
        self.assertEqual(len(total_inv_sale_order), 5)
        for line in sale_order.order_line:
            self.assertEqual(line.qty_delivered, 3)
            self.assertEqual(line.qty_invoiced, 3)
        for line in sale_order_2.order_line:
            self.assertEqual(line.qty_delivered, 3)
            self.assertEqual(line.qty_invoiced, 3)

    def test_callback_same_sale_order(self):
        if "sale.order" not in self.env.registry:
            return True
        product_1, product_2 = self.env["product.product"].create(
            [
                {"name": "product 1", "list_price": 5.0, "invoice_policy": "delivery"},
                {"name": "product 2", "list_price": 10.0, "invoice_policy": "delivery"},
            ]
        )
        # Test pre-computes of lines with order
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    Command.create({"product_id": product_1.id, "product_uom_qty": 5}),
                    Command.create({"product_id": product_2.id, "product_uom_qty": 5}),
                ],
            }
        )

        sale_order.action_confirm()
        self._add_qty_delivered_and_create_invoice(sale_order)
        self._add_qty_delivered_and_create_invoice(sale_order)
        self._add_qty_delivered_and_create_invoice(sale_order)
        self._add_qty_delivered_and_create_invoice(sale_order)
        self._add_qty_delivered_and_create_invoice(sale_order)

        invoices = sale_order.mapped("order_line.invoice_lines.move_id")
        invoices[-1].button_cancel()
        invoices[-2].action_post()

        self.assertEqual(len(invoices), 5)
        for line in sale_order.order_line:
            self.assertEqual(line.qty_delivered, 5)
            self.assertEqual(line.qty_invoiced, 4)

        invoices[:2].do_merge(keep_references=False)

        invoices = sale_order.mapped("order_line.invoice_lines.move_id")

        self.assertEqual(len(invoices), 4)
        for line in sale_order.order_line:
            self.assertEqual(line.qty_delivered, 5)
            self.assertEqual(line.qty_invoiced, 4)

    def test_callback_different_purchase_order(self):
        if "purchase.order" not in self.env.registry:
            return True
        product_1, product_2 = self.env["product.product"].create(
            [
                {"name": "product 1", "list_price": 5.0, "invoice_policy": "delivery"},
                {"name": "product 2", "list_price": 10.0, "invoice_policy": "delivery"},
            ]
        )
        # Test pre-computes of lines with order
        purchase_order = self.env["purchase.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    Command.create({"product_id": product_1.id, "product_qty": 5}),
                    Command.create({"product_id": product_2.id, "product_qty": 5}),
                ],
            }
        )
        purchase_order_2 = purchase_order.copy()

        purchase_order.button_confirm()
        purchase_order_2.button_confirm()

        self._add_qty_received_and_create_invoice(purchase_order)
        self._add_qty_received_and_create_invoice(purchase_order)
        self._add_qty_received_and_create_invoice(purchase_order)
        self._add_qty_received_and_create_invoice(purchase_order_2)
        self._add_qty_received_and_create_invoice(purchase_order_2)
        self._add_qty_received_and_create_invoice(purchase_order_2)

        inv_purchase_order = purchase_order.mapped("order_line.invoice_lines.move_id")
        inv_purchase_order_2 = purchase_order_2.mapped(
            "order_line.invoice_lines.move_id"
        )
        total_inv_purchase_order = inv_purchase_order | inv_purchase_order_2

        self.assertEqual(len(inv_purchase_order), 3)
        self.assertEqual(len(inv_purchase_order_2), 3)
        self.assertEqual(len(total_inv_purchase_order), 6)
        for line in purchase_order.order_line:
            self.assertEqual(line.qty_received, 3)
            self.assertEqual(line.qty_invoiced, 3)
        for line in purchase_order_2.order_line:
            self.assertEqual(line.qty_received, 3)
            self.assertEqual(line.qty_invoiced, 3)

        invoices = inv_purchase_order[:1] | inv_purchase_order_2[:1]
        invoices[:2].do_merge(keep_references=False)

        inv_purchase_order = purchase_order.mapped("order_line.invoice_lines.move_id")
        inv_purchase_order_2 = purchase_order_2.mapped(
            "order_line.invoice_lines.move_id"
        )
        total_inv_purchase_order = inv_purchase_order | inv_purchase_order_2

        self.assertEqual(len(inv_purchase_order), 3)
        self.assertEqual(len(inv_purchase_order_2), 3)
        self.assertEqual(len(total_inv_purchase_order), 5)
        for line in purchase_order.order_line:
            self.assertEqual(line.qty_received, 3)
            self.assertEqual(line.qty_invoiced, 3)
        for line in purchase_order_2.order_line:
            self.assertEqual(line.qty_received, 3)
            self.assertEqual(line.qty_invoiced, 3)

    def test_callback_same_purchase_order(self):
        if "purchase.order" not in self.env.registry:
            return True
        product_1, product_2 = self.env["product.product"].create(
            [
                {"name": "product 1", "list_price": 5.0, "invoice_policy": "delivery"},
                {"name": "product 2", "list_price": 10.0, "invoice_policy": "delivery"},
            ]
        )
        # Test pre-computes of lines with order
        purchase_order = self.env["purchase.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    Command.create({"product_id": product_1.id, "product_qty": 5}),
                    Command.create({"product_id": product_2.id, "product_qty": 5}),
                ],
            }
        )

        purchase_order.button_confirm()
        self._add_qty_received_and_create_invoice(purchase_order)
        self._add_qty_received_and_create_invoice(purchase_order)
        self._add_qty_received_and_create_invoice(purchase_order)
        self._add_qty_received_and_create_invoice(purchase_order)
        self._add_qty_received_and_create_invoice(purchase_order)

        invoices = purchase_order.mapped("order_line.invoice_lines.move_id")
        invoices[-1].button_cancel()
        invoices[-2].write({"invoice_date": fields.Date.today()})
        invoices[-2].action_post()

        self.assertEqual(len(invoices), 5)
        for line in purchase_order.order_line:
            self.assertEqual(line.qty_received, 5)
            self.assertEqual(line.qty_invoiced, 4)

        invoices[:2].do_merge(keep_references=False)

        invoices = purchase_order.mapped("order_line.invoice_lines.move_id")

        self.assertEqual(len(invoices), 4)
        for line in purchase_order.order_line:
            self.assertEqual(line.qty_received, 5)
            self.assertEqual(line.qty_invoiced, 4)

    @mock.patch(
        "odoo.addons.account_invoice_merge.models.account_move.AccountMove.post_merge_message"
    )
    @mock.patch(
        "odoo.addons.account_invoice_merge.models.account_move.AccountMove.post_process_fields"
    )
    def test_account_invoice_merge_4(
        self, mock_post_process_fields, mock_post_merge_message
    ):
        invoices = self.invoice1 | self.invoice2
        wiz_id = self.wiz.with_context(
            active_ids=invoices.ids,
            active_model=invoices._name,
        ).create({})
        wiz_id.get_view()
        wiz_id.merge_invoices()
        mock_post_process_fields.assert_called_once_with(invoices)
        mock_post_merge_message.assert_called_once_with(invoices)

    def test_get_post_merge_message_invoice_identifier(self):
        """Test that the post-merge message invoice identifier is correct."""
        self.assertEqual(
            self.invoice1._get_post_merge_message_invoice_identifier(),
            f"account.move({self.invoice1.id})",
        )

    def test_post_merge_message(self):
        """Test that the post-merge message is displayed when merging invoices."""
        invoices = self.invoice1 | self.invoice2
        invoice_3 = self._create_invoice(self.partner_a, "C")
        message_li_invoice_1 = Markup(
            f"<li><a href=# data-oe-model='account.move' "
            f"data-oe-id='{self.invoice1.id}'>"
            f"{self.invoice1._get_post_merge_message_invoice_identifier()}</a>"
            f" - "
            f"{self.invoice1.amount_total}</li>"
        )
        message_li_invoice_2 = Markup(
            f"<li><a href=# data-oe-model='account.move' "
            f"data-oe-id='{self.invoice2.id}'>"
            f"{self.invoice2._get_post_merge_message_invoice_identifier()}</a>"
            f" - "
            f"{self.invoice2.amount_total}</li>"
        )
        message_body = Markup(
            f"Invoice merged from :"
            f"<ul>{message_li_invoice_1}{message_li_invoice_2}</ul>"
        )
        with patch(
            "odoo.addons.mail.models.mail_thread.MailThread.message_post"
        ) as mock_message_post:
            invoice_3.post_merge_message(invoices)
            self.assertEqual(mock_message_post.call_count, 1)
            self.assertEqual(mock_message_post.call_args[1].get("body"), message_body)

    @patch(
        (
            "odoo.addons.account_invoice_merge.models.account_move.AccountMove."
            "_get_fields_to_concatenate_after_merge"
        ),
        return_value=["ref"],
    )
    def test_post_process_fields(self, mock_get_fields_to_concatenate_after_merge):
        self.invoice1.ref = "Blabla1"
        self.invoice2.ref = "Blabla2"
        invoices = self.invoice1 | self.invoice2
        invoice_3 = self._create_invoice(self.partner_a, "C")
        invoice_3.post_process_fields(invoices)
        self.assertEqual(invoice_3.ref, "Blabla1 // Blabla2")
