from dataclasses import dataclass

from sqlalchemy.orm import Session

from models.streamer import StreamerProductAssignment, StreamerProfile


@dataclass(frozen=True)
class RevenueShareLine:
    saleor_product_id: str
    gross_amount: int


@dataclass(frozen=True)
class StreamerRevenueShare:
    streamer_slug: str
    gross_amount: int
    commission_bps: int
    share_amount: int


@dataclass(frozen=True)
class RevenueSharePreview:
    order_id: str
    shares: list[StreamerRevenueShare]
    unassigned_product_ids: list[str]


class RevenueShareService:
    def __init__(self, db: Session):
        self.db = db

    def preview_order_share(
        self,
        *,
        order_id: str,
        lines: list[RevenueShareLine],
    ) -> RevenueSharePreview:
        normalized_order_id = self._validate_required(order_id, "order_id is required")
        shares_by_streamer: dict[str, StreamerRevenueShare] = {}
        unassigned_product_ids: list[str] = []

        for line in lines:
            product_id = self._validate_required(
                line.saleor_product_id,
                "saleor_product_id is required",
            )
            if line.gross_amount <= 0:
                raise ValueError("gross_amount must be positive")

            assignment = self._get_assignment(product_id)
            if assignment is None:
                unassigned_product_ids.append(product_id)
                continue

            streamer = self.db.get(StreamerProfile, assignment.streamer_profile_id)
            if streamer is None or not streamer.active:
                unassigned_product_ids.append(product_id)
                continue

            share_amount = line.gross_amount * streamer.commission_bps // 10000
            existing_share = shares_by_streamer.get(streamer.slug)
            if existing_share is None:
                shares_by_streamer[streamer.slug] = StreamerRevenueShare(
                    streamer_slug=streamer.slug,
                    gross_amount=line.gross_amount,
                    commission_bps=streamer.commission_bps,
                    share_amount=share_amount,
                )
                continue

            shares_by_streamer[streamer.slug] = StreamerRevenueShare(
                streamer_slug=streamer.slug,
                gross_amount=existing_share.gross_amount + line.gross_amount,
                commission_bps=streamer.commission_bps,
                share_amount=existing_share.share_amount + share_amount,
            )

        return RevenueSharePreview(
            order_id=normalized_order_id,
            shares=list(shares_by_streamer.values()),
            unassigned_product_ids=unassigned_product_ids,
        )

    def _get_assignment(self, saleor_product_id: str) -> StreamerProductAssignment | None:
        return (
            self.db.query(StreamerProductAssignment)
            .filter(StreamerProductAssignment.saleor_product_id == saleor_product_id)
            .one_or_none()
        )

    @staticmethod
    def _validate_required(value: str, message: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(message)
        return normalized
