#    Copyright 2026 SECTRA AB
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""Walk a `WsiMetadata` and fill in unset UIDs using a `UidGenerator`.

Construction-side helper for `wsidicom.metadata.WsiMetadata`. Lives in
wsidicomizer (alongside `WsiDicomizerMetadata.merge`) because both are
"complete a partial WsiMetadata" operations; wsidicom owns the model and
the schemas' `dump_required` contract, wsidicomizer owns the builders that
satisfy it.
"""

from dataclasses import replace

from wsidicom.metadata import (
    Pyramid,
    Series,
    Slide,
    Study,
    UidGenerator,
    WsiMetadata,
)
from wsidicom.metadata.sample import SlideSample


class MetadataUidResolver:
    """Walks a `WsiMetadata` and fills in unset UIDs using a `UidGenerator`.

    Generation order is deterministic across fields: study, series, slide
    samples, pyramid, frame_of_reference, dimension_organization. The order
    matters for generators that count or otherwise depend on call order
    (e.g. counter prefixes).

    Each per-role method receives the entity (or, for WSI-wide UIDs, the
    parent `WsiMetadata`) so the generator can derive UIDs from content —
    hash-based reproducible UIDs, registry lookup by identifier, audit
    logging with context. Already-set UIDs are preserved verbatim.

    Examples
    --------
    Resolve a metadata once and reuse the result across all instances::

        from wsidicom.metadata import CallableUidGenerator
        from wsidicomizer import MetadataUidResolver

        resolver = MetadataUidResolver(CallableUidGenerator(my_callable))
        resolved = resolver.resolve(metadata)
    """

    def __init__(self, generator: UidGenerator):
        self._generator = generator

    def resolve(self, metadata: WsiMetadata) -> WsiMetadata:
        return replace(
            metadata,
            study=self._resolve_study(metadata.study),
            series=self._resolve_series(metadata.series),
            slide=self._resolve_slide(metadata.slide),
            pyramid=self._resolve_pyramid(metadata.pyramid),
            frame_of_reference_uid=(
                metadata.frame_of_reference_uid
                or self._generator.frame_of_reference_uid(metadata)
            ),
            dimension_organization_uids=(
                metadata.dimension_organization_uids
                or [self._generator.dimension_organization_uid(metadata)]
            ),
        )

    def _resolve_study(self, study: Study) -> Study:
        if study.uid is not None:
            return study
        return replace(study, uid=self._generator.study_uid(study))

    def _resolve_series(self, series: Series) -> Series:
        if series.uid is not None:
            return series
        return replace(series, uid=self._generator.series_uid(series))

    def _resolve_slide(self, slide: Slide) -> Slide:
        if not slide.samples:
            return slide
        return replace(
            slide,
            samples=[self._resolve_sample(sample) for sample in slide.samples],
        )

    def _resolve_sample(self, sample: SlideSample) -> SlideSample:
        if sample.uid is not None:
            return sample
        return replace(sample, uid=self._generator.sample_uid(sample))

    def _resolve_pyramid(self, pyramid: Pyramid) -> Pyramid:
        if pyramid.uid is not None:
            return pyramid
        return replace(pyramid, uid=self._generator.pyramid_uid(pyramid))
